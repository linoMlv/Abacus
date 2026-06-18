from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from database import get_session
from dependencies import get_current_association
from models import Association, AssociationRead
from security import get_password_hash, verify_password

router = APIRouter(prefix="/api/account", tags=["account"])


class UpdateAccountRequest(BaseModel):
    name: str | None = None
    email: str | None = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.put("", response_model=AssociationRead)
def update_account(
    request: UpdateAccountRequest,
    current_association: Association = Depends(get_current_association),
    session: Session = Depends(get_session),
):
    if request.name is not None and request.name != current_association.name:
        existing = session.exec(
            select(Association).where(Association.name == request.name)
        ).first()
        if existing:
            raise HTTPException(
                status_code=400, detail="Association name already taken"
            )
        current_association.name = request.name

    if request.email is not None and request.email != current_association.email:
        existing_email = session.exec(
            select(Association).where(Association.email == request.email)
        ).first()
        if existing_email:
            raise HTTPException(status_code=400, detail="Email already in use")
        current_association.email = request.email

    session.add(current_association)
    session.commit()
    session.refresh(current_association)
    return current_association


@router.put("/password")
def change_password(
    request: ChangePasswordRequest,
    current_association: Association = Depends(get_current_association),
    session: Session = Depends(get_session),
):
    if not verify_password(request.current_password, current_association.password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    current_association.password = get_password_hash(request.new_password)
    session.add(current_association)
    session.commit()
    return {"message": "Password updated successfully"}
