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
from typing import Protocol, TypeVar

from fastapi import Depends, HTTPException, status
from jose import JWTError, jwt
from sqlmodel import Session, select

from authz import Permission, effective_permissions
from database import get_session
from dependencies import get_token
from models import Membership, MembershipStatus, PermissionPreset, Role, User
from security import ALGORITHM, SECRET_KEY

USER_TOKEN_TYPE = "user"

_CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def decode_user_token(token: str, session: Session) -> User | None:
    """Resolve the active user a *user* access token identifies, or ``None``.

    The single, non-raising implementation of the token validation core (valid
    JWT, ``type == "user"`` anti-confusion guard, present subject, active user)
    shared by the raising dependency and the optional-auth flows. Hardening it
    here protects every call site at once.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None
    if payload.get("type") != USER_TOKEN_TYPE:
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    user = session.get(User, user_id)
    return user if user is not None and user.is_active else None


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
    user = decode_user_token(token, session)
    if user is None:
        raise _CREDENTIALS_EXCEPTION
    return user


class _TenantOwned(Protocol):
    """A row that belongs to exactly one association (non-null tenant key)."""

    association_id: str


T = TypeVar("T", bound=_TenantOwned)


def owned_or_404(
    session: Session,
    model: type[T],
    obj_id: str,
    association_id: str,
    detail: str = "Introuvable",
) -> T:
    """Fetch ``model`` by id and confirm it belongs to ``association_id``.

    The shared tenant-scoped lookup: an id from the client never authorizes
    access on its own. An object that does not exist *or* belongs to another
    association is reported as ``404`` alike, so the response never leaks the
    existence of another tenant's data.
    """
    obj = session.get(model, obj_id)
    if obj is None or obj.association_id != association_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
    return obj


def find_membership(
    session: Session, association_id: str, user_id: str
) -> Membership | None:
    """The membership of ``user_id`` in ``association_id``, or ``None``.

    The shared (association, user) lookup — distinct from :func:`owned_or_404`,
    which keys on a primary id.
    """
    return session.exec(
        select(Membership).where(
            Membership.association_id == association_id,
            Membership.user_id == user_id,
        )
    ).first()


def preset_permission_set(
    session: Session, association_id: str, preset_id: str | None
) -> frozenset[Permission] | None:
    """The tenant-scoped permission set of a custom preset, or ``None``.

    ``None`` when there is no preset, or the referenced preset is missing or
    belongs to another association — the caller then falls back to the role base.
    The single resolver shared by request authorization and the permissions API.
    """
    if preset_id is None:
        return None
    preset = session.get(PermissionPreset, preset_id)
    if preset is None or preset.association_id != association_id:
        return None
    values = set(preset.permissions)
    return frozenset(p for p in Permission if p.value in values)


@dataclass(frozen=True)
class AccessContext:
    """Authenticated user resolved against one association they may access.

    ``permissions`` is the server-authoritative effective set for this membership
    (role/preset base ± per-member overrides; ADMIN immune) — the single source
    every route and the UI gating should rely on.
    """

    user: User
    association_id: str
    role: Role
    membership: Membership
    permissions: frozenset[Permission]


def _resolve_permissions(
    session: Session, membership: Membership, association_id: str
) -> frozenset[Permission]:
    """Compute the effective permissions of ``membership`` (T8).

    Resolves the assigned custom preset (tenant-scoped; a foreign or missing
    preset falls back to the role base) and applies the per-member overrides via
    :func:`authz.effective_permissions`.
    """
    preset_permissions = preset_permission_set(
        session, association_id, membership.preset_id
    )
    return effective_permissions(
        membership.role, preset_permissions, membership.permission_overrides
    )


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
        permissions=_resolve_permissions(session, membership, association_id),
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
        if permission not in ctx.permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return ctx

    return _dependency
