import uuid
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum

from sqlmodel import Field, Relationship, SQLModel


class OperationType(str, Enum):
    INCOME = "income"
    EXPENSE = "expense"


class Association(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    name: str = Field(unique=True)
    email: str = Field(unique=True)
    password: str

    balances: list["Balance"] = Relationship(back_populates="association")


class Balance(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    name: str
    initialAmount: Decimal = Field(default=0, max_digits=10, decimal_places=2)
    association_id: str | None = Field(default=None, foreign_key="association.id")

    association: Association | None = Relationship(back_populates="balances")
    operations: list["Operation"] = Relationship(
        back_populates="balance",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
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
    email: str
    balances: list[BalanceRead] = []


class ApiKey(SQLModel, table=True):
    __tablename__ = "api_key"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    name: str
    key_hash: str
    key_prefix: str = Field(max_length=8)
    association_id: str = Field(foreign_key="association.id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_used_at: datetime | None = None
    is_active: bool = Field(default=True)

    association: Association | None = Relationship()


class ApiKeyRead(SQLModel):
    id: str
    name: str
    key_prefix: str
    created_at: datetime
    last_used_at: datetime | None
    is_active: bool


class ApiKeyCreated(SQLModel):
    id: str
    name: str
    key: str
    key_prefix: str
    created_at: datetime


class LogEntry(SQLModel, table=True):
    __tablename__ = "log_entry"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    method: str
    path: str
    status_code: int = 0
    ip_address: str | None = None
    user_agent: str | None = None
    user: str | None = None
    duration_ms: float | None = None
    event_type: str | None = None
    detail: str | None = None


class LogEntryRead(SQLModel):
    id: str
    timestamp: datetime
    method: str
    path: str
    status_code: int
    ip_address: str | None
    user_agent: str | None
    user: str | None
    duration_ms: float | None
    event_type: str | None
    detail: str | None
