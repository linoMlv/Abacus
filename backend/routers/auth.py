from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlmodel import Session, select

from database import get_session
from dependencies import get_current_association
from models import (
    Association,
    AssociationRead,
    Balance,
    association_to_read,
)
from security import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    get_password_hash,
    verify_password,
)


class BalanceCreate(BaseModel):
    name: str
    amount: str


class SignupRequest(BaseModel):
    name: str
    password: str
    balances: list[BalanceCreate]


class LoginRequest(BaseModel):
    name: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    association: AssociationRead


router = APIRouter(prefix="/api", tags=["auth"])


@router.post("/signup", response_model=AssociationRead)
def signup(request: SignupRequest, session: Session = Depends(get_session)):
    statement = select(Association).where(Association.name == request.name)
    existing = session.exec(statement).first()
    if existing:
        raise HTTPException(status_code=400, detail="Association already exists")

    hashed_password = get_password_hash(request.password)
    association = Association(name=request.name, password=hashed_password)
    session.add(association)
    session.commit()
    session.refresh(association)

    for b in request.balances:
        balance = Balance(
            name=b.name,
            initialAmount=float(b.amount),
            association_id=association.id,
            position=0,
        )
        session.add(balance)

    session.commit()
    session.refresh(association)
    return association_to_read(association)


@router.post("/login", response_model=LoginResponse)
def login(
    response: Response, request: LoginRequest, session: Session = Depends(get_session)
):
    statement = select(Association).where(Association.name == request.name)
    association = session.exec(statement).first()
    if not association or not verify_password(request.password, association.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": association.name}, expires_delta=access_token_expires
    )

    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        expires=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax",
        secure=False,
    )

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        association=association_to_read(association),
    )


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("access_token")
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=AssociationRead)
def read_users_me(current_association: Association = Depends(get_current_association)):
    return association_to_read(current_association)
