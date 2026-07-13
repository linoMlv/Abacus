import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from sqlmodel import Field, SQLModel

from .common import utcnow


class LigneBancaireStatut(str, Enum):
    """Reconciliation state of a statement line. Stable strings (persisted)."""

    NON_RAPPROCHE = "non_rapproche"  # not yet matched to an entry
    RAPPROCHE = "rapproche"  # lettré: linked to an accounting entry
    IGNORE = "ignore"  # deliberately set aside (handled elsewhere)


class ImportReleve(SQLModel, table=True):
    """One bank-statement import batch, bound to a treasury account (§5)."""

    __tablename__ = "import_releve"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    association_id: str = Field(foreign_key="association.id", index=True)
    compte_id: str = Field(foreign_key="compte.id", index=True)  # treasury account
    filename: str
    nb_lignes: int = Field(default=0)
    imported_by: str | None = Field(default=None, foreign_key="user.id")
    created_at: datetime = Field(default_factory=utcnow)


class LigneBancaire(SQLModel, table=True):
    """A single statement movement, reconciled (lettré) to an entry or not."""

    __tablename__ = "ligne_bancaire"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    association_id: str = Field(foreign_key="association.id", index=True)
    import_id: str = Field(foreign_key="import_releve.id", index=True)
    compte_id: str = Field(foreign_key="compte.id", index=True)  # treasury account
    date_operation: date
    libelle: str
    # Signed: >0 = inflow (credit on the bank account), <0 = outflow.
    montant: Decimal = Field(max_digits=12, decimal_places=2)
    # Bank's unique transaction id (OFX only, null for CSV): dedup key so a
    # re-import overlapping a previous one does not insert the same movement twice.
    fitid: str | None = Field(default=None, index=True)
    statut: LigneBancaireStatut = Field(default=LigneBancaireStatut.NON_RAPPROCHE)
    # The accounting entry this line is lettré to (set only when RAPPROCHE).
    ecriture_id: str | None = Field(default=None, foreign_key="ecriture.id", index=True)
    rapproche_by: str | None = Field(default=None, foreign_key="user.id")
    rapproche_at: datetime | None = None


class ImportReleveRead(SQLModel):
    id: str
    compte_id: str
    filename: str
    nb_lignes: int
    created_at: datetime


class LigneBancaireRead(SQLModel):
    id: str
    import_id: str
    compte_id: str
    date_operation: date
    libelle: str
    montant: Decimal
    statut: LigneBancaireStatut
    ecriture_id: str | None


class RapprochementSuggestion(SQLModel):
    """An existing entry that matches a statement line (same signed amount)."""

    ecriture_id: str
    numero_piece: int
    date: date
    libelle: str
    montant: Decimal  # signed net on the treasury account (matches the line)


class RapprochementCompteRead(SQLModel):
    """Reconciliation state of one treasury account (page Comptes, C25).

    ``solde_bancaire_estime`` is what the bank should show: the books plus the
    movements the bank reported and nobody has booked yet. When every line is
    reconciled the two coincide — that is the whole point of the screen.
    """

    compte_id: str
    numero: str
    libelle: str
    solde_comptable: Decimal
    nb_non_rapprochees: int
    montant_non_rapproche: Decimal
    solde_bancaire_estime: Decimal
    dernier_import: datetime | None
