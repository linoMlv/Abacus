import uuid
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel


def _utcnow() -> datetime:
    return datetime.now(UTC)


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


class RefreshSession(SQLModel, table=True):
    __tablename__ = "refresh_session"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    association_id: str = Field(foreign_key="association.id")
    token_hash: str = Field(unique=True, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime
    revoked_at: datetime | None = None
    user_agent: str | None = None
    ip_address: str | None = None


class LogEntry(SQLModel, table=True):
    __tablename__ = "log_entry"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)
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


# ---------------------------------------------------------------------------
# Identity & access (V3 multi-association, RBAC)
#
# A User is a physical person with a single global identity. Access to an
# association is granted exclusively through a Membership, which also carries
# the Role. The same person can therefore hold different roles across several
# associations. The role/permission mapping lives in ``authz.py``.
# ---------------------------------------------------------------------------


class Role(str, Enum):
    """Role held by a user *within a given association* (carried by Membership).

    Values are stable strings: they are persisted and may appear in audit
    trails and exports — do not rename them.
    """

    ADMIN = "admin"  # administre l'asso : membres, paramètres, logs (superset)
    ACCOUNTANT = "accountant"  # expert-comptable : saisie manuelle, validation, clôture
    TREASURER = "treasurer"  # trésorier : saisie assistée, banque, dons, budget
    VIEWER = "viewer"  # président / CA : consultation seule


class MembershipStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"  # accès gelé sans suppression (révocable)


class User(SQLModel, table=True):
    __tablename__ = "user"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    # Stored normalized (lowercased) by the auth layer; unique identity key.
    email: str = Field(unique=True, index=True)
    password: str
    name: str
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=_utcnow)


class Membership(SQLModel, table=True):
    __tablename__ = "membership"
    # A user holds at most one membership (and thus one role) per association.
    __table_args__ = (
        UniqueConstraint("user_id", "association_id", name="uq_membership_user_assoc"),
    )

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    association_id: str = Field(foreign_key="association.id", index=True)
    role: Role
    status: MembershipStatus = Field(default=MembershipStatus.ACTIVE)
    invited_by: str | None = Field(default=None, foreign_key="user.id")
    created_at: datetime = Field(default_factory=_utcnow)


class Invitation(SQLModel, table=True):
    __tablename__ = "invitation"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    association_id: str = Field(foreign_key="association.id", index=True)
    # Normalized (lowercased) target email; a User may not exist yet.
    email: str = Field(index=True)
    role: Role
    # Only the hash of the invitation token is stored, never the raw token.
    token_hash: str = Field(unique=True, index=True)
    invited_by: str = Field(foreign_key="user.id")
    created_at: datetime = Field(default_factory=_utcnow)
    expires_at: datetime
    accepted_at: datetime | None = None


class MembershipRead(SQLModel):
    id: str
    association_id: str
    role: Role
    status: MembershipStatus
