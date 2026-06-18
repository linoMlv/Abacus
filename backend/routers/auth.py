from datetime import timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from database import get_session
from dependencies import get_current_association
from email_service import send_password_reset_email
from rate_limit import AUTH_RATE_LIMIT, limiter
from models import (
    Association,
    AssociationRead,
    Balance,
)
from security import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    ALGORITHM,
    SECRET_KEY,
    create_access_token,
    get_password_hash,
    verify_password,
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

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": association.name}, expires_delta=access_token_expires
    )

    from security import ENVIRONMENT

    is_secure = ENVIRONMENT == "production"

    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        expires=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax",
        secure=is_secure,
    )

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        association=association,
    )


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("access_token")
    return {"message": "Logged out successfully"}


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

    from datetime import UTC, datetime

    from jose import jwt as jose_jwt

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
    from jose import JWTError
    from jose import jwt as jose_jwt

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
    session.commit()
    return {"message": "Password has been reset successfully"}
