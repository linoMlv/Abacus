from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from datetime import datetime
from pydantic import BaseModel

from database import get_session
from models import Operation, OperationType, Balance, Association
from dependencies import get_current_association

router = APIRouter(prefix="/api/operations", tags=["operations"])

class OperationCreate(BaseModel):
    name: str
    description: str
    group: str
    amount: float
    type: OperationType
    date: datetime
    balance_id: str
    invoice: str | None = None

class OperationUpdate(BaseModel):
    name: str
    description: str
    group: str
    amount: float
    type: OperationType
    date: datetime
    balance_id: str
    invoice: str | None = None

@router.post("")
def create_operation(
    op: OperationCreate, 
    session: Session = Depends(get_session),
    current_association: Association = Depends(get_current_association)
):
    balance = session.get(Balance, op.balance_id)
    if not balance:
        raise HTTPException(status_code=404, detail="Balance not found")
    
    if balance.association_id != current_association.id:
         raise HTTPException(status_code=403, detail="Not authorized to add operation to this balance")

    operation = Operation(
        name=op.name,
        description=op.description,
        group=op.group,
        amount=op.amount,
        type=op.type,
        date=op.date,
        balance_id=op.balance_id,
        invoice=op.invoice
    )
    session.add(operation)
    session.commit()
    session.refresh(operation)
    return operation

@router.delete("/{operation_id}")
def delete_operation(
    operation_id: str, 
    session: Session = Depends(get_session),
    current_association: Association = Depends(get_current_association)
):
    operation = session.get(Operation, operation_id)
    if not operation:
        raise HTTPException(status_code=404, detail="Operation not found")
    
    balance = session.get(Balance, operation.balance_id)
    if not balance or balance.association_id != current_association.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this operation")

    session.delete(operation)
    session.commit()
    return {"ok": True}

@router.put("/{operation_id}")
def update_operation(
    operation_id: str, 
    op: OperationUpdate, 
    session: Session = Depends(get_session),
    current_association: Association = Depends(get_current_association)
):
    operation = session.get(Operation, operation_id)
    if not operation:
        raise HTTPException(status_code=404, detail="Operation not found")
    
    balance = session.get(Balance, operation.balance_id)
    if not balance or balance.association_id != current_association.id:
         raise HTTPException(status_code=403, detail="Not authorized to update this operation")
    
    if op.balance_id != operation.balance_id:
        new_balance = session.get(Balance, op.balance_id)
        if not new_balance or new_balance.association_id != current_association.id:
            raise HTTPException(status_code=403, detail="Not authorized to move to this balance")

    operation.name = op.name
    operation.description = op.description
    operation.group = op.group
    operation.amount = op.amount
    operation.type = op.type
    operation.date = op.date
    operation.balance_id = op.balance_id
    operation.invoice = op.invoice
    
    session.add(operation)
    session.commit()
    session.refresh(operation)
    return operation
