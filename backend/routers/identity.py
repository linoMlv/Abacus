"""V3 identity & access API: user accounts, associations, memberships.

Namespaced apart from the legacy association-login endpoints during the
strangler migration:

* ``/api/auth/*``           — user account & session.
* ``/api/asso/{id}/*``      — association-scoped access (URL scoping), guarded
                              by :func:`auth_context.get_active_membership`.
"""

import hashlib
import os
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy import update
from sqlmodel import Session, select

from accounting_seed import seed_association_accounting
from auth_context import (
    USER_TOKEN_TYPE,
    AccessContext,
    get_active_membership,
    get_current_user,
    require_permission,
)
from authz import Permission
from database import get_session
from email_service import send_invitation_email
from models import (
    Association,
    Invitation,
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
    ALGORITHM,
    COOKIE_SECURE,
    REFRESH_TOKEN_EXPIRE_DAYS,
    SECRET_KEY,
    create_access_token,
    generate_refresh_token,
    get_password_hash,
    hash_refresh_token,
    password_needs_rehash,
    validate_password_strength,
    verify_password,
)

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
COOKIE_PATH = "/api"
INVITATION_EXPIRE_DAYS = int(os.getenv("INVITATION_EXPIRE_DAYS", "7"))


def _utcnow() -> datetime:
    """Naive UTC, matching how datetimes are stored in the DB."""
    return datetime.now(UTC).replace(tzinfo=None)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


router = APIRouter(tags=["identity"])


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #
class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


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


class CreateInvitationRequest(BaseModel):
    email: str
    role: Role


class InvitationRead(BaseModel):
    id: str
    email: str
    role: Role
    created_at: datetime
    expires_at: datetime
    accepted_at: datetime | None


class InvitationCreated(InvitationRead):
    # The raw token is returned once, to the inviting admin, so a link can be
    # shared directly in addition to the e-mail.
    token: str


class AcceptInvitationRequest(BaseModel):
    token: str
    name: str | None = None
    password: str | None = None


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


def _revoke_user_sessions(session: Session, user_id: str) -> None:
    """Revoke every active refresh session of a user (no commit)."""
    session.exec(
        update(RefreshSession)
        .where(
            RefreshSession.user_id == user_id,
            RefreshSession.revoked_at.is_(None),
        )
        .values(revoked_at=_utcnow())
    )


def _user_session_by_token(session: Session, raw_refresh: str) -> RefreshSession | None:
    """Look up a *user* refresh session by raw token (ignores legacy sessions)."""
    return session.exec(
        select(RefreshSession).where(
            RefreshSession.token_hash == hash_refresh_token(raw_refresh),
            RefreshSession.user_id.is_not(None),
        )
    ).first()


def _optional_current_user(request: Request, session: Session) -> User | None:
    """Resolve the authenticated user if any, without raising (for accept flow)."""
    raw = request.cookies.get(ACCESS_COOKIE)
    if not raw:
        header = request.headers.get("authorization")
        if header and header.lower().startswith("bearer "):
            raw = header
    if not raw:
        return None
    token = raw.split(" ", 1)[1] if raw.startswith("Bearer ") else raw
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
    return user if user and user.is_active else None


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
def _check_password_strength(password: str) -> None:
    """Enforce the password policy, surfacing a 400 on a weak password."""
    try:
        validate_password_strength(password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/api/auth/register", response_model=UserRead, status_code=201)
def register(request: RegisterRequest, session: Session = Depends(get_session)):
    _check_password_strength(request.password)
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

    # Transparently upgrade a legacy/outdated hash now that we have the plaintext.
    if password_needs_rehash(user.password):
        user.password = get_password_hash(credentials.password)
        session.add(user)
        session.commit()

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
    _revoke_user_sessions(session, user.id)
    session.commit()
    response.delete_cookie(ACCESS_COOKIE, path=COOKIE_PATH)
    response.delete_cookie(REFRESH_COOKIE, path=COOKIE_PATH)
    return {"message": "All sessions revoked"}


@router.post("/api/auth/change-password")
def change_password(
    request: Request,
    response: Response,
    body: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Change the current user's password and revoke all other sessions.

    Requires the current password. On success the stored hash is updated and
    *every* refresh session is revoked (locking out a thief on another device);
    a fresh session is then issued for the current device so the caller stays
    signed in here.
    """
    if not verify_password(body.current_password, user.password):
        raise HTTPException(status_code=400, detail="Mot de passe actuel incorrect.")
    _check_password_strength(body.new_password)

    user.password = get_password_hash(body.new_password)
    session.add(user)
    _revoke_user_sessions(session, user.id)
    session.commit()

    _issue_user_session(response, user, request, session)
    return {"message": "Password changed"}


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
    # Seed the default chart of accounts, journals and current fiscal year.
    seed_association_accounting(session, association.id)
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


# --------------------------------------------------------------------------- #
# Invitations
# --------------------------------------------------------------------------- #
def _invitation_read(invitation: Invitation) -> InvitationRead:
    return InvitationRead(
        id=invitation.id,
        email=invitation.email,
        role=invitation.role,
        created_at=invitation.created_at,
        expires_at=invitation.expires_at,
        accepted_at=invitation.accepted_at,
    )


@router.post(
    "/api/asso/{association_id}/invitations",
    response_model=InvitationCreated,
    status_code=201,
)
def create_invitation(
    request: CreateInvitationRequest,
    ctx: AccessContext = Depends(require_permission(Permission.MEMBER_MANAGE)),
    session: Session = Depends(get_session),
):
    email = _normalize_email(request.email)

    # Reject inviting someone who is already a member of this association.
    existing_user = session.exec(select(User).where(User.email == email)).first()
    if existing_user and _get_membership(session, ctx.association_id, existing_user.id):
        raise HTTPException(status_code=400, detail="This person is already a member")

    # Keep a single live invitation per (association, email): drop prior ones.
    prior = session.exec(
        select(Invitation).where(
            Invitation.association_id == ctx.association_id,
            Invitation.email == email,
            Invitation.accepted_at.is_(None),
        )
    ).all()
    for old in prior:
        session.delete(old)

    raw_token = secrets.token_urlsafe(32)
    invitation = Invitation(
        association_id=ctx.association_id,
        email=email,
        role=request.role,
        token_hash=_hash_token(raw_token),
        invited_by=ctx.user.id,
        expires_at=_utcnow() + timedelta(days=INVITATION_EXPIRE_DAYS),
    )
    session.add(invitation)
    session.commit()
    session.refresh(invitation)

    association = session.get(Association, ctx.association_id)
    send_invitation_email(email, association.name, raw_token)

    return InvitationCreated(
        **_invitation_read(invitation).model_dump(), token=raw_token
    )


@router.get(
    "/api/asso/{association_id}/invitations",
    response_model=list[InvitationRead],
)
def list_invitations(
    ctx: AccessContext = Depends(require_permission(Permission.MEMBER_MANAGE)),
    session: Session = Depends(get_session),
):
    invitations = session.exec(
        select(Invitation).where(
            Invitation.association_id == ctx.association_id,
            Invitation.accepted_at.is_(None),
        )
    ).all()
    return [_invitation_read(inv) for inv in invitations]


@router.delete("/api/asso/{association_id}/invitations/{invitation_id}")
def revoke_invitation(
    invitation_id: str,
    ctx: AccessContext = Depends(require_permission(Permission.MEMBER_MANAGE)),
    session: Session = Depends(get_session),
):
    invitation = session.get(Invitation, invitation_id)
    # Scope check: never reveal/affect another association's invitations.
    if invitation is None or invitation.association_id != ctx.association_id:
        raise HTTPException(status_code=404, detail="Invitation not found")

    session.delete(invitation)
    session.commit()
    return {"message": "Invitation revoked"}


@router.post("/api/auth/invitations/accept", response_model=SessionResponse)
def accept_invitation(
    request: Request,
    response: Response,
    body: AcceptInvitationRequest,
    session: Session = Depends(get_session),
):
    invitation = session.exec(
        select(Invitation).where(Invitation.token_hash == _hash_token(body.token))
    ).first()
    now = _utcnow()
    invalid = HTTPException(status_code=400, detail="Invalid or expired invitation")
    if (
        not invitation
        or invitation.accepted_at is not None
        or invitation.expires_at < now
    ):
        raise invalid

    email = invitation.email
    user = session.exec(select(User).where(User.email == email)).first()
    current = _optional_current_user(request, session)
    issue_session = False

    if user is not None:
        # The invitation targets an existing account; the caller must be it.
        if current is None:
            raise HTTPException(
                status_code=401,
                detail="Please log in as the invited account to accept",
            )
        if current.id != user.id:
            raise HTTPException(
                status_code=403, detail="This invitation is for another account"
            )
        acting = user
    else:
        # No account yet: create one on the fly from the invitation email.
        if not body.name or not body.password:
            raise HTTPException(
                status_code=400,
                detail="Account creation requires name and password",
            )
        _check_password_strength(body.password)
        acting = User(
            email=email,
            password=get_password_hash(body.password),
            name=body.name,
        )
        session.add(acting)
        session.commit()
        session.refresh(acting)
        issue_session = True

    if _get_membership(session, invitation.association_id, acting.id) is None:
        session.add(
            Membership(
                user_id=acting.id,
                association_id=invitation.association_id,
                role=invitation.role,
                invited_by=invitation.invited_by,
            )
        )
    invitation.accepted_at = now
    session.add(invitation)
    session.commit()

    if issue_session:
        _issue_user_session(response, acting, request, session)

    return SessionResponse(
        user=UserRead(id=acting.id, email=acting.email, name=acting.name),
        associations=_associations_for(session, acting),
    )
