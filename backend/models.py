import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum

from sqlmodel import Field, Relationship, SQLModel


class OperationType(str, Enum):
    INCOME = "income"
    EXPENSE = "expense"


class Association(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    name: str = Field(unique=True)
    password: str

    balances: list["Balance"] = Relationship(back_populates="association")


class Balance(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    name: str
    initialAmount: Decimal = Field(default=0, max_digits=10, decimal_places=2)
    association_id: str | None = Field(default=None, foreign_key="association.id")

    association: Association | None = Relationship(back_populates="balances")
    operations: list["Operation"] = Relationship(
        back_populates="balance", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    position: int = Field(default=0)


class Operation(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    name: str
    description: str
    group: str
    amount: Decimal = Field(default=0, max_digits=10, decimal_places=2)
    type: OperationType
    date: datetime
    invoice: str | None = None
    balance_id: str | None = Field(default=None, foreign_key="balance.id")

    balance: Balance | None = Relationship(back_populates="operations")


class BalanceRead(SQLModel):
    id: str
    name: str
    initialAmount: Decimal
    position: int = 0


class AssociationRead(SQLModel):
    id: str
    name: str
    balances: list[BalanceRead] = []



