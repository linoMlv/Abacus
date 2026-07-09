import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint
from sqlmodel import Field, SQLModel

from .common import utcnow


class Association(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    name: str = Field(unique=True)
    # Contact e-mail only (no longer a login identity since the V2 removal), so it
    # is not globally unique: two associations may legitimately share a contact.
    email: str = Field(index=True)
    # Vestige of V2 association-login (removed): V3 associations have no password.
    password: str | None = Field(default=None)
    # Whether the association is subject to VAT (§4). Off by default: most
    # associations are exempt, and while off every VAT field/column/account is
    # hidden and the engine never books a 4456x line.
    regime_tva: bool = Field(default=False)
    # Fiscal identity, used to issue tax receipts (§8): postal address and legal
    # identifiers (RNA "W…", SIRET), plus the association's stated purpose. All
    # optional; the receipt endpoint requires the mandatory ones to be filled.
    adresse: str | None = None
    code_postal: str | None = None
    ville: str | None = None
    rna: str | None = None
    siret: str | None = None
    objet: str | None = None


class RefreshSession(SQLModel, table=True):
    __tablename__ = "refresh_session"
    # Owner XOR: exactly one of user_id / association_id is set (B12). Enforced in
    # the DB so a malformed session (no owner, or two owners) can never persist.
    __table_args__ = (
        CheckConstraint(
            "(user_id IS NULL) <> (association_id IS NULL)",
            name="ck_refresh_session_one_owner",
        ),
    )

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    # Exactly one of association_id (legacy) / user_id (V3) identifies the owner.
    association_id: str | None = Field(default=None, foreign_key="association.id")
    user_id: str | None = Field(default=None, foreign_key="user.id", index=True)
    token_hash: str = Field(unique=True, index=True)
    created_at: datetime = Field(default_factory=utcnow)
    expires_at: datetime
    revoked_at: datetime | None = None
    user_agent: str | None = None
    ip_address: str | None = None


class LogEntry(SQLModel, table=True):
    __tablename__ = "log_entry"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    timestamp: datetime = Field(default_factory=utcnow, index=True)
    method: str
    path: str
    status_code: int = 0
    ip_address: str | None = None
    user_agent: str | None = None
    user: str | None = None
    # Association targeted by the request (parsed from /api/asso/{id}/...), so
    # an admin can read the logs scoped to their own association. Plain string
    # (no FK): logging must never fail on an arbitrary/garbage path id.
    association_id: str | None = Field(default=None, index=True)
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
    association_id: str | None
    duration_ms: float | None
    event_type: str | None
    detail: str | None


class AuditLog(SQLModel, table=True):
    """Tamper-evidence trail of sensitive actions (who did what, when).

    Distinct from the HTTP ``LogEntry``: this records business actions (entry
    created/validated/deleted, …) for accounting integrity (plan §10). Scoped by
    ``association_id`` so an admin only ever reads their own tenant's trail.
    """

    __tablename__ = "audit_log"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    timestamp: datetime = Field(default_factory=utcnow, index=True)
    association_id: str | None = Field(
        default=None, foreign_key="association.id", index=True
    )
    actor_user_id: str | None = Field(default=None, foreign_key="user.id")
    action: str = Field(index=True)  # e.g. "ecriture.validate"
    target_type: str | None = None  # e.g. "ecriture"
    target_id: str | None = None
    detail: str | None = None


class AuditLogRead(SQLModel):
    id: str
    timestamp: datetime
    actor_user_id: str | None
    action: str
    target_type: str | None
    target_id: str | None
    detail: str | None
