import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from .common import utcnow


class EvenementStatut(str, Enum):
    """Lifecycle of an event. Stable strings (persisted, audited)."""

    ACTIF = "actif"
    CLOTURE = "cloture"


class Evenement(SQLModel, table=True):
    """An analytic axis (§15.6): an action/project (Gala 2026…) tagging entries.

    Groups the recettes and dépenses of an action, independently of the chart of
    accounts, so its result (Σ produits − Σ charges on tagged entries) can be
    compared to an optional budget. Distinct from réglementaire ``fonds dédiés``
    (19x): this is a *piloting* layer. One entry belongs to at most one event.
    """

    __tablename__ = "evenement"
    __table_args__ = (
        UniqueConstraint("association_id", "nom", name="uq_evenement_assoc_nom"),
    )

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    association_id: str = Field(foreign_key="association.id", index=True)
    nom: str
    description: str | None = None
    date_debut: date | None = None
    date_fin: date | None = None
    budget_recettes: Decimal | None = Field(
        default=None, max_digits=12, decimal_places=2
    )
    budget_depenses: Decimal | None = Field(
        default=None, max_digits=12, decimal_places=2
    )
    statut: EvenementStatut = Field(default=EvenementStatut.ACTIF)
    couleur: str | None = None  # UI accent, e.g. "#7C3AED"
    created_at: datetime = Field(default_factory=utcnow)


class EvenementRead(SQLModel):
    id: str
    nom: str
    description: str | None
    date_debut: date | None
    date_fin: date | None
    budget_recettes: Decimal | None
    budget_depenses: Decimal | None
    statut: EvenementStatut
    couleur: str | None
    # Computed from tagged entries (never stored): produits (cl.7) / charges (cl.6).
    realise_recettes: Decimal
    realise_depenses: Decimal
    resultat: Decimal  # realise_recettes − realise_depenses
