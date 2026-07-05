import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from .common import utcnow
from .ecriture import ModeReglement


class FormeDon(str, Enum):
    """Nature of the donation on a tax receipt (Cerfa). Stable strings."""

    NUMERAIRE = "numeraire"  # argent
    TITRES = "titres"  # titres de sociétés
    AUTRE = "autre"  # abandon de frais, dons en nature…


class RecuFiscal(SQLModel, table=True):
    """A donation tax receipt (reçu fiscal, art. 200/238 bis CGI, §8).

    Attached to one or more validated recette entries (the dons) via
    ``RecuFiscalLigne``; it snapshots the donor, amount, form and issue date. The
    accounting truth stays on the linked entries — this is the legal document.
    """

    __tablename__ = "recu_fiscal"
    __table_args__ = (
        UniqueConstraint("association_id", "numero", name="uq_recu_assoc_numero"),
    )

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    association_id: str = Field(foreign_key="association.id", index=True)
    numero: int  # sequential order number per association (gapless)
    tiers_id: str = Field(foreign_key="tiers.id", index=True)  # the donor
    date: date  # issue date
    annee: int  # fiscal year the dons relate to
    montant: Decimal = Field(max_digits=10, decimal_places=2)
    forme: FormeDon = Field(default=FormeDon.NUMERAIRE)
    mode_reglement: ModeReglement | None = None
    # A receipt is never hard-deleted (its order number must never be reused): it
    # is cancelled, which frees its dons but keeps the numbered row and its trail.
    annule: bool = Field(default=False)
    created_by: str | None = Field(default=None, foreign_key="user.id")
    created_at: datetime = Field(default_factory=utcnow)


class RecuFiscalLigne(SQLModel, table=True):
    """Links a receipt to a don entry. Unique on ``ecriture_id`` so a given don
    can appear on at most one receipt (no double tax deduction)."""

    __tablename__ = "recu_fiscal_ligne"
    __table_args__ = (
        UniqueConstraint("ecriture_id", name="uq_recu_ligne_ecriture"),
    )

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    recu_fiscal_id: str = Field(foreign_key="recu_fiscal.id", index=True)
    ecriture_id: str = Field(foreign_key="ecriture.id", index=True)


class RecuFiscalRead(SQLModel):
    id: str
    numero: int
    tiers_id: str
    tiers_nom: str
    date: date
    annee: int
    montant: Decimal
    forme: FormeDon
    mode_reglement: ModeReglement | None
    annule: bool


class DonRead(SQLModel):
    """A donation eligible for a receipt: a validated recette entry with a donor."""

    ecriture_id: str
    date: date
    numero_piece: int
    libelle: str
    montant: Decimal
    tiers_id: str
    tiers_nom: str
    recu_id: str | None  # set when already on a receipt
    recu_numero: int | None
