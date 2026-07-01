"""User account & session endpoints (``/api/auth/*``)."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlmodel import Session, select

from auth_context import get_current_user
from database import get_session
from models import User
from rate_limit import AUTH_RATE_LIMIT, limiter
from security import (
    get_password_hash,
    password_needs_rehash,
    verify_password,
)

from .helpers import (
    ACCESS_COOKIE,
    COOKIE_PATH,
    REFRESH_COOKIE,
    _check_password_strength,
    _issue_user_session,
    _normalize_email,
    _revoke_user_sessions,
    _session_response,
    _user_session_by_token,
    _utcnow,
)
from .schemas import (
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
    SessionResponse,
    UserRead,
)

router = APIRouter(tags=["identity"])


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
    return _session_response(session, user)


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
    return _session_response(session, user)


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
    return _session_response(session, user)
