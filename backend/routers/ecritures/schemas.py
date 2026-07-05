"""Request/response bodies for the accounting-entry endpoints."""

from datetime import date
from decimal import Decimal

from sqlmodel import SQLModel

from models import EcritureDetailRead, ModeReglement


class SaisieSimpleRequest(SQLModel):
    categorie_id: str
    compte_tresorerie_id: str
    montant: Decimal
    date: date
    libelle: str | None = None
    tiers_id: str | None = None
    evenement_id: str | None = None
    reference_externe: str | None = None
    mode_reglement: ModeReglement | None = None
    # VAT rate override (percent). Honoured only when the régime TVA is on; else
    # the category default applies. The montant is read as TTC when a rate applies.
    tva_taux: Decimal | None = None


class VirementRequest(SQLModel):
    compte_source_id: str
    compte_destination_id: str
    montant: Decimal
    date: date
    libelle: str | None = None
    reference_externe: str | None = None
    mode_reglement: ModeReglement | None = None


class LigneInput(SQLModel):
    compte_id: str
    libelle: str | None = None
    debit: Decimal = Decimal("0")
    credit: Decimal = Decimal("0")


class SaisieManuelleRequest(SQLModel):
    journal_id: str
    date: date
    libelle: str
    lignes: list[LigneInput]
    tiers_id: str | None = None
    evenement_id: str | None = None
    reference_externe: str | None = None
    mode_reglement: ModeReglement | None = None


class EcritureContenu(SQLModel):
    """Origine-specific entry content; exactly one variant must be set.

    Reused by draft edition (``PATCH``) and contre-passation replacement: the
    variant provided must match the entry's origine, so the same builder/validation
    path produces the lines whatever the write path.
    """

    simple: SaisieSimpleRequest | None = None
    virement: VirementRequest | None = None
    manuelle: SaisieManuelleRequest | None = None


class ContrepassationRequest(SQLModel):
    """Optional corrected entry to book alongside the reversal (annule-et-remplace)."""

    remplacement: EcritureContenu | None = None


class ContrepassationRead(SQLModel):
    """The reversal (always) and, for annule-et-remplace, the corrected entry."""

    extourne: EcritureDetailRead
    remplacement: EcritureDetailRead | None = None


class BulkIdsRequest(SQLModel):
    ids: list[str]


class BulkIgnore(SQLModel):
    id: str
    raison: str


class BulkResult(SQLModel):
    """Outcome of a best-effort bulk action: processed ids and ignored ones."""

    traitees: list[str]
    ignorees: list[BulkIgnore]
