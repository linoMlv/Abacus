"""Request bodies for the recurring-entry endpoints."""

from datetime import date
from decimal import Decimal

from sqlmodel import SQLModel

from models import ModeReglement, Periodicite, RecurrenceMode


class RecurrenceCreate(SQLModel):
    libelle: str
    categorie_id: str
    compte_tresorerie_id: str
    montant: Decimal
    periodicite: Periodicite
    prochaine_echeance: date
    tiers_id: str | None = None
    evenement_id: str | None = None
    reference_externe: str | None = None
    mode_reglement: ModeReglement | None = None
    date_fin: date | None = None
    mode: RecurrenceMode = RecurrenceMode.PROPOSITION


class RecurrenceUpdate(SQLModel):
    """Partial update; only provided fields change (``exclude_unset``)."""

    libelle: str | None = None
    categorie_id: str | None = None
    compte_tresorerie_id: str | None = None
    montant: Decimal | None = None
    periodicite: Periodicite | None = None
    prochaine_echeance: date | None = None
    date_fin: date | None = None
    mode: RecurrenceMode | None = None
    actif: bool | None = None
    tiers_id: str | None = None
    evenement_id: str | None = None
    reference_externe: str | None = None
    mode_reglement: ModeReglement | None = None
