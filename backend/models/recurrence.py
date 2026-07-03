import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from sqlmodel import Field, SQLModel

from .common import utcnow
from .ecriture import ModeReglement


class Periodicite(str, Enum):
    """How often a recurrence falls due. Stable strings (persisted)."""

    HEBDOMADAIRE = "hebdomadaire"
    MENSUELLE = "mensuelle"
    TRIMESTRIELLE = "trimestrielle"
    ANNUELLE = "annuelle"


class RecurrenceMode(str, Enum):
    """What happens at each due date. Stable strings (persisted)."""

    PROPOSITION = "proposition"  # a draft is proposed, the user validates it
    AUTO = "auto"  # the entry is booked and validated directly (safe cases)


class Recurrence(SQLModel, table=True):
    """A recurring recette/dépense template (loyer, abonnement, cotisation…).

    Holds a *simple entry* model (category → account, treasury account, amount…)
    plus a schedule. A daily job (and a manual trigger) books the entries that
    have fallen due, advancing ``prochaine_echeance`` each time — idempotent, so a
    run never duplicates an occurrence.
    """

    __tablename__ = "recurrence"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    association_id: str = Field(foreign_key="association.id", index=True)
    libelle: str
    # The simple-entry model: category (carries the sens + produit/charge account)
    # posted against a treasury account, for a fixed amount.
    categorie_id: str = Field(foreign_key="categorie_saisie.id")
    compte_tresorerie_id: str = Field(foreign_key="compte.id")
    montant: Decimal = Field(max_digits=12, decimal_places=2)
    tiers_id: str | None = Field(default=None, foreign_key="tiers.id")
    evenement_id: str | None = Field(default=None, foreign_key="evenement.id")
    reference_externe: str | None = None
    mode_reglement: ModeReglement | None = None
    # Schedule.
    periodicite: Periodicite
    prochaine_echeance: date
    date_fin: date | None = None
    mode: RecurrenceMode = Field(default=RecurrenceMode.PROPOSITION)
    actif: bool = Field(default=True)
    created_by: str | None = Field(default=None, foreign_key="user.id")
    created_at: datetime = Field(default_factory=utcnow)
    derniere_generation: date | None = None


class RecurrenceRead(SQLModel):
    id: str
    libelle: str
    categorie_id: str
    compte_tresorerie_id: str
    montant: Decimal
    tiers_id: str | None
    evenement_id: str | None
    reference_externe: str | None
    mode_reglement: ModeReglement | None
    periodicite: Periodicite
    prochaine_echeance: date
    date_fin: date | None
    mode: RecurrenceMode
    actif: bool


class GenerationResult(SQLModel):
    """Outcome of a generation pass: how many entries were booked."""

    generees: int
