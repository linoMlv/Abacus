"""Tenant-scoped access control for the V3 user/association model.

The single, server-authoritative gate through which every association-scoped
request must pass. Responsibilities, in order:

1. Authenticate the **user** from the access token (``get_current_user``).
2. Resolve the **active association** from the URL path (``{association_id}``).
3. Verify the user holds an **active Membership** for that association.
4. Expose ``(user, association_id, role, membership)`` as an ``AccessContext``.

Security rules:

* The ``association_id`` from the path is an *indication*, never an
  authorization: access is granted only by an active ``Membership`` resolved
  server-side. Callers must additionally scope their queries by
  ``ctx.association_id``.
* No tenant-existence leak: a non-member receives ``404`` whether or not the
  association exists. A suspended member receives ``403``.
* Token confusion is prevented: only access tokens minted for users (``type ==
  "user"``) are accepted here; legacy association tokens are rejected.
"""

from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from jose import JWTError, jwt
from sqlmodel import Session, select

from authz import Permission, has_permission
from database import get_session
from dependencies import get_token
from models import Membership, MembershipStatus, Role, User
from security import ALGORITHM, SECRET_KEY

USER_TOKEN_TYPE = "user"

_CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    token: str | None = Depends(get_token),
    session: Session = Depends(get_session),
) -> User:
    """Resolve the authenticated, active user from the access token."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise _CREDENTIALS_EXCEPTION

    # Reject anything that is not a user access token (defense against
    # confusing a legacy association token for a user identity).
    if payload.get("type") != USER_TOKEN_TYPE:
        raise _CREDENTIALS_EXCEPTION
    user_id = payload.get("sub")
    if not user_id:
        raise _CREDENTIALS_EXCEPTION

    user = session.get(User, user_id)
    if user is None or not user.is_active:
        raise _CREDENTIALS_EXCEPTION
    return user


@dataclass(frozen=True)
class AccessContext:
    """Authenticated user resolved against one association they may access."""

    user: User
    association_id: str
    role: Role
    membership: Membership


def get_active_membership(
    association_id: str,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> AccessContext:
    """Authorize ``user`` for the association named in the path.

    Returns ``404`` for a non-member (no existence leak) and ``403`` for a
    suspended member.
    """
    membership = session.exec(
        select(Membership).where(
            Membership.user_id == user.id,
            Membership.association_id == association_id,
        )
    ).first()

    if membership is None:
        # Do not reveal whether the association exists.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Association not found"
        )
    if membership.status != MembershipStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Membership is not active"
        )

    return AccessContext(
        user=user,
        association_id=association_id,
        role=membership.role,
        membership=membership,
    )


def require_permission(permission: Permission):
    """Dependency factory: require ``permission`` within the active association.

    Usage::

        @router.get("/api/asso/{association_id}/members")
        def list_members(ctx=Depends(require_permission(Permission.MEMBER_MANAGE))):
            ...
    """

    def _dependency(
        ctx: AccessContext = Depends(get_active_membership),
    ) -> AccessContext:
        if not has_permission(ctx.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return ctx

    return _dependency
