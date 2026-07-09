"""Shared cookie/session/lookup helpers for the identity endpoints."""

import os
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, Request, Response
from sqlalchemy import update
from sqlmodel import Session, select

from auth_context import USER_TOKEN_TYPE, decode_user_token
from models import (
    Association,
    Invitation,
    Membership,
    MembershipStatus,
    RefreshSession,
    Role,
    User,
)
from request_utils import client_ip
from security import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    COOKIE_SECURE,
    REFRESH_TOKEN_EXPIRE_DAYS,
    create_access_token,
    generate_refresh_token,
    hash_refresh_token,
    validate_password_strength,
)

from .schemas import AssociationSummary, InvitationRead, SessionResponse, UserRead

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
COOKIE_PATH = "/api"
INVITATION_EXPIRE_DAYS = int(os.getenv("INVITATION_EXPIRE_DAYS", "7"))
# Per-account brute-force lockout: after this many consecutive failed logins the
# account is locked for this many minutes (complements the per-IP rate limit).
LOGIN_MAX_ATTEMPTS = int(os.getenv("LOGIN_MAX_ATTEMPTS", "5"))
LOGIN_LOCKOUT_MINUTES = int(os.getenv("LOGIN_LOCKOUT_MINUTES", "15"))


def _utcnow() -> datetime:
    """Naive UTC, matching how datetimes are stored in the DB."""
    return datetime.now(UTC).replace(tzinfo=None)


def _is_locked(user: User, now: datetime) -> bool:
    """True while the account is under a brute-force lockout."""
    return user.locked_until is not None and user.locked_until > now


def _register_failed_login(session: Session, user: User) -> None:
    """Count a failed login; lock the account once the threshold is crossed."""
    user.failed_login_count += 1
    if user.failed_login_count >= LOGIN_MAX_ATTEMPTS:
        user.locked_until = _utcnow() + timedelta(minutes=LOGIN_LOCKOUT_MINUTES)
        user.failed_login_count = 0
    session.add(user)
    session.commit()


def _reset_login_attempts(session: Session, user: User) -> None:
    """Clear any failed-login state after a successful login."""
    if user.failed_login_count or user.locked_until is not None:
        user.failed_login_count = 0
        user.locked_until = None
        session.add(user)
        session.commit()


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
    return decode_user_token(token, session)


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


def _session_response(session: Session, user: User) -> SessionResponse:
    return SessionResponse(
        user=UserRead(id=user.id, email=user.email, name=user.name),
        associations=_associations_for(session, user),
    )


def _check_password_strength(password: str) -> None:
    """Enforce the password policy, surfacing a 400 on a weak password."""
    try:
        validate_password_strength(password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


def _invitation_read(invitation: Invitation) -> InvitationRead:
    return InvitationRead(
        id=invitation.id,
        email=invitation.email,
        role=invitation.role,
        created_at=invitation.created_at,
        expires_at=invitation.expires_at,
        accepted_at=invitation.accepted_at,
    )
