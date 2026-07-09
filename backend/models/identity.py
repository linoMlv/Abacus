import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel

from .common import utcnow


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
    created_at: datetime = Field(default_factory=utcnow)
    # Brute-force lockout: consecutive failed logins and, once the threshold is
    # crossed, the (naive UTC) instant until which login is refused (429).
    failed_login_count: int = Field(default=0)
    locked_until: datetime | None = Field(default=None)


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
    created_at: datetime = Field(default_factory=utcnow)
    # Fine-grained access (T8): an optional custom preset that replaces the role's
    # permission base, plus a per-member ``{permission_value: bool}`` override map
    # (grant=True / revoke=False). Effective permissions are computed server-side
    # in ``authz.effective_permissions`` (ADMIN stays immune). Cf. plan §2/§15.10.
    preset_id: str | None = Field(
        default=None, foreign_key="permission_preset.id", index=True
    )
    permission_overrides: dict[str, bool] = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False)
    )


class PermissionPreset(SQLModel, table=True):
    """A reusable, association-owned named permission set (custom role, T8).

    Assigned to a ``Membership`` via ``preset_id`` to replace the built-in role's
    permission base; per-member overrides then refine it. Tenant-scoped; its name
    is unique per association. ``permissions`` holds stable permission *values*
    (``domain:action``); unknown values are ignored when computing effective sets.
    """

    __tablename__ = "permission_preset"
    __table_args__ = (
        UniqueConstraint("association_id", "nom", name="uq_preset_assoc_nom"),
    )

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    association_id: str = Field(foreign_key="association.id", index=True)
    nom: str
    permissions: list[str] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False)
    )
    created_at: datetime = Field(default_factory=utcnow)


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
    created_at: datetime = Field(default_factory=utcnow)
    expires_at: datetime
    accepted_at: datetime | None = None


class MembershipRead(SQLModel):
    id: str
    association_id: str
    role: Role
    status: MembershipStatus
