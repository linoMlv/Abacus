import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from .common import utcnow


class TypeTiers(str, Enum):
    """Kind of third party (§3). Stable strings (persisted, audited)."""

    FOURNISSEUR = "fournisseur"
    CLIENT = "client"  # usagers, adhérents, clients
    DONATEUR = "donateur"
    FINANCEUR = "financeur"  # subventions, mécénat
    AUTRE = "autre"


class Tiers(SQLModel, table=True):
    """A third party the association deals with (supplier, member, donor…).

    A lightweight informative entity for now: a name and a type, attached to an
    entry to enable "by tiers" views. The accounting third-party ledger (401/411
    linkage, lettrage) is a later concern.
    """

    __tablename__ = "tiers"
    __table_args__ = (
        UniqueConstraint("association_id", "nom", name="uq_tiers_assoc_nom"),
    )

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    association_id: str = Field(foreign_key="association.id", index=True)
    type: TypeTiers
    nom: str
    # Postal address (optional) — needed on a donor's tax receipt (§8).
    adresse: str | None = None
    code_postal: str | None = None
    ville: str | None = None
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=utcnow)


class TiersRead(SQLModel):
    id: str
    type: TypeTiers
    nom: str
    adresse: str | None
    code_postal: str | None
    ville: str | None
    is_active: bool
