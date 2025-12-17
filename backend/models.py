from typing import List, Optional
from sqlmodel import Field, Relationship, SQLModel
from enum import Enum
import uuid
from datetime import datetime

class OperationType(str, Enum):
    INCOME = 'income'
    EXPENSE = 'expense'

class Association(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    name: str
    password: str
    
    balances: List["Balance"] = Relationship(back_populates="association")

class Balance(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    name: str
    initialAmount: float
    association_id: Optional[str] = Field(default=None, foreign_key="association.id")
    
    association: Optional[Association] = Relationship(back_populates="balances")
    operations: List["Operation"] = Relationship(back_populates="balance")
    position: int = Field(default=0)

class Operation(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    name: str
    description: str
    group: str
    amount: float
    type: OperationType
    date: datetime
    invoice: Optional[str] = None
    balance_id: Optional[str] = Field(default=None, foreign_key="balance.id")
    
    balance: Optional[Balance] = Relationship(back_populates="operations")

class BalanceRead(SQLModel):
    id: str
    name: str
    initialAmount: float
    position: int = 0
    operations: List[Operation] = []

class AssociationRead(SQLModel):
    id: str
    name: str
    balances: List[BalanceRead] = []
    operations: List[Operation] = []

def association_to_read(association: Association) -> AssociationRead:
    all_operations = []
    balance_reads = []
    for balance in association.balances:
        ops = balance.operations
        all_operations.extend(ops)
        balance_reads.append(BalanceRead(
            id=balance.id,
            name=balance.name,
            initialAmount=balance.initialAmount,
            position=balance.position,
            operations=ops
        ))
    
    return AssociationRead(
        id=association.id,
        name=association.name,
        balances=balance_reads,
        operations=all_operations
    )
