import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel

from .common import utcnow


class ApiKey(SQLModel, table=True):
    """A machine credential for the MCP server (Phase 6, plan §7).

    A key is bound to a ``Membership``: it acts as that member and inherits their
    *effective* permissions, recomputed live on every request (role/preset ±
    overrides). Revoking a permission from the member, suspending or removing the
    membership therefore disables the matching key access immediately — the key
    holds no frozen authority of its own.

    Only the SHA-256 ``key_hash`` is stored; the raw ``abk_…`` secret is shown
    once at creation and never again. ``prefix`` (``abk_`` + a few chars) is kept
    in clear only to let a human recognise a key in the listing.
    """

    __tablename__ = "api_key"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    association_id: str = Field(foreign_key="association.id", index=True)
    membership_id: str = Field(foreign_key="membership.id", index=True)
    name: str
    prefix: str
    key_hash: str = Field(unique=True, index=True)
    created_by: str = Field(foreign_key="user.id")
    created_at: datetime = Field(default_factory=utcnow)
    last_used_at: datetime | None = None
    # Soft revocation: the row is kept (audit + the hash stays reserved) but the
    # resolver treats a key with ``revoked_at`` set as non-existent.
    revoked_at: datetime | None = None


class ApiKeyRead(SQLModel):
    """A key as returned to the admin panel — never carries the raw secret."""

    id: str
    name: str
    prefix: str
    membership_id: str
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None
    # Enriched by the router for display (the member the key acts as).
    role: str | None = None
    member_name: str | None = None
    member_email: str | None = None


class ApiKeyCreated(ApiKeyRead):
    """The one-time creation response: the raw secret, shown exactly once."""

    key: str
