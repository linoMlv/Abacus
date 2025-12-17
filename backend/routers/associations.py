from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from database import get_session
from dependencies import get_current_association
from models import Association, AssociationRead, Balance, association_to_read

router = APIRouter(prefix="/api/associations", tags=["associations"])


@router.get("/{association_id}", response_model=AssociationRead)
def get_association(
    association_id: str,
    session: Session = Depends(get_session),
    current_association: Association = Depends(get_current_association),
):
    if current_association.id != association_id:
        raise HTTPException(
            status_code=403, detail="Not authorized to view this association"
        )

    statement = (
        select(Association)
        .where(Association.id == association_id)
        .options(selectinload(Association.balances).selectinload(Balance.operations))
    )
    association = session.exec(statement).first()

    if not association:
        raise HTTPException(status_code=404, detail="Association not found")

    return association_to_read(association)
