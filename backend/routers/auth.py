from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from jose import JWTError
from jose import jwt as jose_jwt
from pydantic import BaseModel
from sqlalchemy import update
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from database import get_session
from dependencies import get_current_association
from email_service import send_password_reset_email
from models import (
    Association,
    AssociationRead,
    Balance,
    RefreshSession,
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
    verify_password,
)

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
COOKIE_PATH = "/api"


def _utcnow() -> datetime:
    """Naive UTC, matching how datetimes are stored in the DB."""
    return datetime.now(UTC).replace(tzinfo=None)


def _issue_session(
    response: Response,
    association: Association,
    request: Request,
    session: Session,
) -> str:
    """Set a fresh access cookie and create a refresh session cookie."""
    access_token = create_access_token(
        data={"sub": association.name},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    response.set_cookie(
        key=ACCESS_COOKIE,
        value=f"Bearer {access_token}",
        httponly=True,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax",
        secure=COOKIE_SECURE,
        path=COOKIE_PATH,
    )

    raw_refresh = generate_refresh_token()
    refresh_session = RefreshSession(
        association_id=association.id,
        token_hash=hash_refresh_token(raw_refresh),
        expires_at=_utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        user_agent=request.headers.get("user-agent"),
        ip_address=client_ip(request),
    )
    session.add(refresh_session)
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
    return access_token


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path=COOKIE_PATH)
    response.delete_cookie(REFRESH_COOKIE, path=COOKIE_PATH)


def _session_by_token(session: Session, raw_refresh: str) -> RefreshSession | None:
    return session.exec(
        select(RefreshSession).where(
            RefreshSession.token_hash == hash_refresh_token(raw_refresh)
        )
    ).first()


def _revoke_active_sessions(session: Session, association_id: str) -> None:
    """Revoke every active refresh session for an association (no commit)."""
    session.exec(
        update(RefreshSession)
        .where(
            RefreshSession.association_id == association_id,
            RefreshSession.revoked_at.is_(None),
        )
        .values(revoked_at=_utcnow())
    )


class BalanceCreate(BaseModel):
    name: str
    amount: str


class SignupRequest(BaseModel):
    name: str
    email: str
    password: str
    balances: list[BalanceCreate]


class LoginRequest(BaseModel):
    name: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    association: AssociationRead


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    password: str


router = APIRouter(prefix="/api", tags=["auth"])


@router.post("/signup", response_model=AssociationRead)
def signup(request: SignupRequest, session: Session = Depends(get_session)):
    statement = select(Association).where(Association.name == request.name)
    existing = session.exec(statement).first()
    if existing:
        raise HTTPException(status_code=400, detail="Association already exists")

    existing_email = session.exec(
        select(Association).where(Association.email == request.email)
    ).first()
    if existing_email:
        raise HTTPException(status_code=400, detail="Email already in use")

    hashed_password = get_password_hash(request.password)
    association = Association(
        name=request.name, email=request.email, password=hashed_password
    )
    session.add(association)
    session.commit()
    session.refresh(association)

    for b in request.balances:
        balance = Balance(
            name=b.name,
            initialAmount=Decimal(b.amount),
            association_id=association.id,
            position=0,
        )
        session.add(balance)

    session.commit()
    session.refresh(association)
    return association


@router.post("/login", response_model=LoginResponse)
@limiter.limit(AUTH_RATE_LIMIT)
def login(
    request: Request,
    response: Response,
    credentials: LoginRequest,
    session: Session = Depends(get_session),
):
    statement = (
        select(Association)
        .where(Association.name == credentials.name)
        .options(selectinload(Association.balances))
    )
    association = session.exec(statement).first()
    if not association or not verify_password(
        credentials.password, association.password
    ):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = _issue_session(response, association, request, session)

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        association=association,
    )


@router.post("/refresh", response_model=LoginResponse)
def refresh(
    request: Request, response: Response, session: Session = Depends(get_session)
):
    raw_refresh = request.cookies.get(REFRESH_COOKIE)
    invalid = HTTPException(status_code=401, detail="Invalid refresh token")
    if not raw_refresh:
        raise invalid

    refresh_session = _session_by_token(session, raw_refresh)
    now = _utcnow()
    if (
        not refresh_session
        or refresh_session.revoked_at is not None
        or refresh_session.expires_at < now
    ):
        raise invalid

    association = session.exec(
        select(Association)
        .where(Association.id == refresh_session.association_id)
        .options(selectinload(Association.balances))
    ).first()
    if not association:
        raise invalid

    # Rotate: revoke the used token before issuing a new session.
    refresh_session.revoked_at = now
    session.add(refresh_session)

    access_token = _issue_session(response, association, request, session)
    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        association=association,
    )


@router.post("/logout")
def logout(
    request: Request, response: Response, session: Session = Depends(get_session)
):
    raw_refresh = request.cookies.get(REFRESH_COOKIE)
    if raw_refresh:
        refresh_session = _session_by_token(session, raw_refresh)
        if refresh_session and refresh_session.revoked_at is None:
            refresh_session.revoked_at = _utcnow()
            session.add(refresh_session)
            session.commit()
    _clear_auth_cookies(response)
    return {"message": "Logged out successfully"}


@router.post("/logout-all")
def logout_all(
    response: Response,
    current_association: Association = Depends(get_current_association),
    session: Session = Depends(get_session),
):
    """Revoke every active refresh session for the current association."""
    _revoke_active_sessions(session, current_association.id)
    session.commit()
    _clear_auth_cookies(response)
    return {"message": "All sessions revoked"}


@router.get("/me", response_model=AssociationRead)
def read_users_me(current_association: Association = Depends(get_current_association)):
    return current_association


@router.post("/forgot-password")
@limiter.limit(AUTH_RATE_LIMIT)
def forgot_password(
    request: Request,
    data: ForgotPasswordRequest,
    session: Session = Depends(get_session),
):
    statement = select(Association).where(Association.email == data.email)
    association = session.exec(statement).first()
    # Always return success to prevent email enumeration
    if not association:
        return {
            "message": (
                "If an account with this email exists, a reset link has been sent."
            )
        }

    token = jose_jwt.encode(
        {
            "sub": association.name,
            "purpose": "reset",
            "exp": datetime.now(UTC) + timedelta(minutes=15),
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )
    send_password_reset_email(association.email, token)
    return {
        "message": "If an account with this email exists, a reset link has been sent."
    }


@router.post("/reset-password")
def reset_password(
    request: ResetPasswordRequest, session: Session = Depends(get_session)
):
    try:
        payload = jose_jwt.decode(request.token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("purpose") != "reset":
            raise HTTPException(status_code=400, detail="Invalid token")
        name = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    statement = select(Association).where(Association.name == name)
    association = session.exec(statement).first()
    if not association:
        raise HTTPException(status_code=400, detail="Invalid token")

    association.password = get_password_hash(request.password)
    session.add(association)
    # Revoke existing refresh sessions so a reset locks out any active intruder.
    _revoke_active_sessions(session, association.id)
    session.commit()
    return {"message": "Password has been reset successfully"}
