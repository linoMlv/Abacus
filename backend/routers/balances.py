from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from database import get_session
from dependencies import get_current_association
from models import Association, Balance, Operation

router = APIRouter(prefix="/api", tags=["balances"])


class BalanceAddRequest(BaseModel):
    name: str
    initialAmount: Decimal
    association_id: str


class BalanceUpdate(BaseModel):
    name: str
    initialAmount: Decimal
    position: int


class BalanceReorderItem(BaseModel):
    id: str
    position: int

class BalanceReorderRequest(BaseModel):
    balances: list[BalanceReorderItem]


@router.post("/balances_add")
def add_balance(
    request: BalanceAddRequest,
    session: Session = Depends(get_session),
    current_association: Association = Depends(get_current_association),
):
    if request.association_id != current_association.id:
        raise HTTPException(
            status_code=403, detail="Not authorized to add balance to this association"
        )

    statement = (
        select(Balance)
        .where(Balance.association_id == request.association_id)
        .order_by(Balance.position.desc())
    )
    last_balance = session.exec(statement).first()
    new_position = (last_balance.position + 1) if last_balance else 0

    balance = Balance(
        name=request.name,
        initialAmount=request.initialAmount,
        association_id=request.association_id,
        position=new_position,
    )
    session.add(balance)
    session.commit()
    session.refresh(balance)
    return balance


@router.delete("/balances/{balance_id}")
def delete_balance(
    balance_id: str,
    session: Session = Depends(get_session),
    current_association: Association = Depends(get_current_association),
):
    balance = session.get(Balance, balance_id)
    if not balance:
        raise HTTPException(status_code=404, detail="Balance not found")

    if balance.association_id != current_association.id:
        raise HTTPException(
            status_code=403, detail="Not authorized to delete this balance"
        )

    if balance.operations:
        raise HTTPException(
            status_code=400, detail="Cannot delete a balance containing operations. Please delete or move them first."
        )

    session.delete(balance)
    session.commit()
    return {"ok": True}


@router.put("/balances/{balance_id}")
def update_balance(
    balance_id: str,
    data: BalanceUpdate,
    session: Session = Depends(get_session),
    current_association: Association = Depends(get_current_association),
):
    balance = session.get(Balance, balance_id)
    if not balance:
        raise HTTPException(status_code=404, detail="Balance not found")

    if balance.association_id != current_association.id:
        raise HTTPException(
            status_code=403, detail="Not authorized to update this balance"
        )

    balance.name = data.name
    balance.initialAmount = data.initialAmount
    balance.position = data.position

    session.add(balance)
    session.commit()
    session.refresh(balance)
    return balance


@router.get("/balances/{balance_id}/operations")
def get_balance_operations(
    balance_id: str,
    skip: int = 0,
    limit: int = 50,
    session: Session = Depends(get_session),
    current_association: Association = Depends(get_current_association),
):
    balance = session.get(Balance, balance_id)
    if not balance or balance.association_id != current_association.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this balance")

    statement = select(Operation).where(Operation.balance_id == balance_id).order_by(Operation.date.desc()).offset(skip).limit(limit)
    return session.exec(statement).all()


@router.put("/balances/reorder")
def reorder_balances(
    request: BalanceReorderRequest,
    session: Session = Depends(get_session),
    current_association: Association = Depends(get_current_association),
):
    for item in request.balances:
        balance = session.get(Balance, item.id)
        if balance and balance.association_id == current_association.id:
            balance.position = item.position
            session.add(balance)
    session.commit()
    return {"ok": True}
