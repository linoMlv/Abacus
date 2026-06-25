"""V3 identity & access API: user accounts, associations, memberships.

Namespaced apart from the legacy association-login endpoints during the
strangler migration:

* ``/api/auth/*``           — user account & session.
* ``/api/asso/{id}/*``      — association-scoped access (URL scoping), guarded
                              by :func:`auth_context.get_active_membership`.
"""

import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import update
from sqlmodel import Session, select

from auth_context import (
    USER_TOKEN_TYPE,
    AccessContext,
    get_active_membership,
    get_current_user,
    require_permission,
)
from authz import Permission
from database import get_session
from models import (
    Association,
    Membership,
    MembershipStatus,
    RefreshSession,
    Role,
    User,
)
from rate_limit import AUTH_RATE_LIMIT, limiter
from request_utils import client_ip
from security import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    COOKIE_SECURE,
    REFRESH_TOKEN_EXPIRE_DAYS,
    create_access_token,
    generate_refresh_token,
    get_password_hash,
    hash_refresh_token,
    verify_password,
)

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
COOKIE_PATH = "/api"


def _utcnow() -> datetime:
    """Naive UTC, matching how datetimes are stored in the DB."""
    return datetime.now(UTC).replace(tzinfo=None)


router = APIRouter(tags=["identity"])


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #
class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str


class LoginRequest(BaseModel):
    email: str
    password: str


class UserRead(BaseModel):
    id: str
    email: str
    name: str


class AssociationSummary(BaseModel):
    id: str
    name: str
    role: Role
    status: MembershipStatus


class SessionResponse(BaseModel):
    user: UserRead
    associations: list[AssociationSummary]


class CreateAssociationRequest(BaseModel):
    name: str
    email: str


class AssociationContext(BaseModel):
    id: str
    name: str
    role: Role


class MemberRead(BaseModel):
    user_id: str
    email: str
    name: str
    role: Role
    status: MembershipStatus


class UpdateMemberRequest(BaseModel):
    role: Role | None = None
    status: MembershipStatus | None = None


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _issue_access_cookie(response: Response, user: User) -> str:
    token = create_access_token(
        data={"sub": user.id, "type": USER_TOKEN_TYPE},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    response.set_cookie(
        key=ACCESS_COOKIE,
        value=f"Bearer {token}",
        httponly=True,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax",
        secure=COOKIE_SECURE,
        path=COOKIE_PATH,
    )
    return token


def _issue_user_session(
    response: Response, user: User, request: Request, session: Session
) -> None:
    """Set a fresh access cookie and create a revocable refresh session."""
    _issue_access_cookie(response, user)

    raw_refresh = generate_refresh_token()
    session.add(
        RefreshSession(
            user_id=user.id,
            token_hash=hash_refresh_token(raw_refresh),
            expires_at=_utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
            user_agent=request.headers.get("user-agent"),
            ip_address=client_ip(request),
        )
    )
    session.commit()

    response.set_cookie(
        key=REFRESH_COOKIE,
        value=raw_refresh,
        httponly=True,
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        samesite="lax",
        secure=COOKIE_SECURE,
        path=COOKIE_PATH,
    )


def _user_session_by_token(session: Session, raw_refresh: str) -> RefreshSession | None:
    """Look up a *user* refresh session by raw token (ignores legacy sessions)."""
    return session.exec(
        select(RefreshSession).where(
            RefreshSession.token_hash == hash_refresh_token(raw_refresh),
            RefreshSession.user_id.is_not(None),
        )
    ).first()


def _get_membership(
    session: Session, association_id: str, user_id: str
) -> Membership | None:
    return session.exec(
        select(Membership).where(
            Membership.association_id == association_id,
            Membership.user_id == user_id,
        )
    ).first()


def _is_last_active_admin(session: Session, membership: Membership) -> bool:
    """True if ``membership`` is the only active admin of its association.

    Used to forbid demoting/suspending/removing the last administrator, which
    would leave the association without anyone able to manage it.
    """
    if membership.role != Role.ADMIN or membership.status != MembershipStatus.ACTIVE:
        return False
    other_admin = session.exec(
        select(Membership).where(
            Membership.association_id == membership.association_id,
            Membership.role == Role.ADMIN,
            Membership.status == MembershipStatus.ACTIVE,
            Membership.user_id != membership.user_id,
        )
    ).first()
    return other_admin is None


def _associations_for(session: Session, user: User) -> list[AssociationSummary]:
    rows = session.exec(
        select(Membership, Association)
        .join(Association, Association.id == Membership.association_id)
        .where(Membership.user_id == user.id)
    ).all()
    return [
        AssociationSummary(id=assoc.id, name=assoc.name, role=m.role, status=m.status)
        for m, assoc in rows
    ]


# --------------------------------------------------------------------------- #
# Account & session
# --------------------------------------------------------------------------- #
@router.post("/api/auth/register", response_model=UserRead, status_code=201)
def register(request: RegisterRequest, session: Session = Depends(get_session)):
    email = _normalize_email(request.email)
    existing = session.exec(select(User).where(User.email == email)).first()
    if existing:
        # Generic message: do not confirm which emails are registered.
        raise HTTPException(status_code=400, detail="Unable to register")

    user = User(
        email=email,
        password=get_password_hash(request.password),
        name=request.name,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return UserRead(id=user.id, email=user.email, name=user.name)


@router.post("/api/auth/login", response_model=SessionResponse)
@limiter.limit(AUTH_RATE_LIMIT)
def login(
    request: Request,
    response: Response,
    credentials: LoginRequest,
    session: Session = Depends(get_session),
):
    email = _normalize_email(credentials.email)
    user = session.exec(select(User).where(User.email == email)).first()
    if not user or not verify_password(credentials.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    _issue_user_session(response, user, request, session)
    return SessionResponse(
        user=UserRead(id=user.id, email=user.email, name=user.name),
        associations=_associations_for(session, user),
    )


@router.post("/api/auth/refresh", response_model=SessionResponse)
def refresh(
    request: Request, response: Response, session: Session = Depends(get_session)
):
    raw_refresh = request.cookies.get(REFRESH_COOKIE)
    invalid = HTTPException(status_code=401, detail="Invalid refresh token")
    if not raw_refresh:
        raise invalid

    refresh_session = _user_session_by_token(session, raw_refresh)
    now = _utcnow()
    if (
        not refresh_session
        or refresh_session.revoked_at is not None
        or refresh_session.expires_at < now
    ):
        raise invalid

    user = session.get(User, refresh_session.user_id)
    if not user or not user.is_active:
        raise invalid

    # Rotate: revoke the used token before issuing a new session.
    refresh_session.revoked_at = now
    session.add(refresh_session)

    _issue_user_session(response, user, request, session)
    return SessionResponse(
        user=UserRead(id=user.id, email=user.email, name=user.name),
        associations=_associations_for(session, user),
    )


@router.post("/api/auth/logout")
def logout(
    request: Request, response: Response, session: Session = Depends(get_session)
):
    raw_refresh = request.cookies.get(REFRESH_COOKIE)
    if raw_refresh:
        refresh_session = _user_session_by_token(session, raw_refresh)
        if refresh_session and refresh_session.revoked_at is None:
            refresh_session.revoked_at = _utcnow()
            session.add(refresh_session)
            session.commit()
    response.delete_cookie(ACCESS_COOKIE, path=COOKIE_PATH)
    response.delete_cookie(REFRESH_COOKIE, path=COOKIE_PATH)
    return {"message": "Logged out"}


@router.post("/api/auth/logout-all")
def logout_all(
    response: Response,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Revoke every active refresh session for the current user (all devices)."""
    session.exec(
        update(RefreshSession)
        .where(
            RefreshSession.user_id == user.id,
            RefreshSession.revoked_at.is_(None),
        )
        .values(revoked_at=_utcnow())
    )
    session.commit()
    response.delete_cookie(ACCESS_COOKIE, path=COOKIE_PATH)
    response.delete_cookie(REFRESH_COOKIE, path=COOKIE_PATH)
    return {"message": "All sessions revoked"}


@router.get("/api/auth/session", response_model=SessionResponse)
def session_info(
    user: User = Depends(get_current_user), session: Session = Depends(get_session)
):
    return SessionResponse(
        user=UserRead(id=user.id, email=user.email, name=user.name),
        associations=_associations_for(session, user),
    )


# --------------------------------------------------------------------------- #
# Associations
# --------------------------------------------------------------------------- #
@router.get("/api/auth/associations", response_model=list[AssociationSummary])
def my_associations(
    user: User = Depends(get_current_user), session: Session = Depends(get_session)
):
    return _associations_for(session, user)


@router.post(
    "/api/auth/associations", response_model=AssociationSummary, status_code=201
)
def create_association(
    request: CreateAssociationRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    if session.exec(
        select(Association).where(Association.name == request.name)
    ).first():
        raise HTTPException(status_code=400, detail="Association name already taken")

    email = _normalize_email(request.email)
    if session.exec(select(Association).where(Association.email == email)).first():
        raise HTTPException(status_code=400, detail="Email already in use")

    association = Association(
        name=request.name,
        email=email,
        # V3 associations have no login of their own; store an unusable secret
        # so the legacy association-login path can never authenticate them.
        password=get_password_hash(secrets.token_urlsafe(32)),
    )
    session.add(association)
    session.commit()
    session.refresh(association)

    membership = Membership(
        user_id=user.id, association_id=association.id, role=Role.ADMIN
    )
    session.add(membership)
    session.commit()

    return AssociationSummary(
        id=association.id,
        name=association.name,
        role=membership.role,
        status=membership.status,
    )


@router.get("/api/asso/{association_id}", response_model=AssociationContext)
def association_context(
    ctx: AccessContext = Depends(get_active_membership),
    session: Session = Depends(get_session),
):
    association = session.get(Association, ctx.association_id)
    # An active membership guarantees the association exists.
    return AssociationContext(id=association.id, name=association.name, role=ctx.role)


@router.get("/api/asso/{association_id}/members", response_model=list[MemberRead])
def list_members(
    ctx: AccessContext = Depends(require_permission(Permission.MEMBER_MANAGE)),
    session: Session = Depends(get_session),
):
    rows = session.exec(
        select(Membership, User)
        .join(User, User.id == Membership.user_id)
        .where(Membership.association_id == ctx.association_id)
    ).all()
    return [
        MemberRead(
            user_id=user.id,
            email=user.email,
            name=user.name,
            role=m.role,
            status=m.status,
        )
        for m, user in rows
    ]


@router.patch("/api/asso/{association_id}/members/{user_id}", response_model=MemberRead)
def update_member(
    user_id: str,
    request: UpdateMemberRequest,
    ctx: AccessContext = Depends(require_permission(Permission.MEMBER_MANAGE)),
    session: Session = Depends(get_session),
):
    membership = _get_membership(session, ctx.association_id, user_id)
    if membership is None:
        raise HTTPException(status_code=404, detail="Member not found")

    new_role = request.role if request.role is not None else membership.role
    new_status = request.status if request.status is not None else membership.status

    # Never strand an association without an administrator.
    leaves_admin = new_role != Role.ADMIN or new_status != MembershipStatus.ACTIVE
    if leaves_admin and _is_last_active_admin(session, membership):
        raise HTTPException(
            status_code=400, detail="Cannot remove the last administrator"
        )

    membership.role = new_role
    membership.status = new_status
    session.add(membership)
    session.commit()
    session.refresh(membership)

    user = session.get(User, user_id)
    return MemberRead(
        user_id=user.id,
        email=user.email,
        name=user.name,
        role=membership.role,
        status=membership.status,
    )


@router.delete("/api/asso/{association_id}/members/{user_id}")
def remove_member(
    user_id: str,
    ctx: AccessContext = Depends(require_permission(Permission.MEMBER_MANAGE)),
    session: Session = Depends(get_session),
):
    membership = _get_membership(session, ctx.association_id, user_id)
    if membership is None:
        raise HTTPException(status_code=404, detail="Member not found")

    if _is_last_active_admin(session, membership):
        raise HTTPException(
            status_code=400, detail="Cannot remove the last administrator"
        )

    session.delete(membership)
    session.commit()
    return {"message": "Member removed"}
