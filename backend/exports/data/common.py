"""Shared primitives for the export data gatherers."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlmodel import Session

from accounting_engine import (
    CLASSE_CHARGE,
    CLASSE_PRODUIT,
    CLASSES_BILAN,
    find_open_exercice,
    to_decimal,
)

# Aliases of the shared accounting roles (single source: accounting_engine).
_CHARGE, _PRODUIT = CLASSE_CHARGE, CLASSE_PRODUIT
_BALANCE_CLASSES = CLASSES_BILAN
_dec = to_decimal


@dataclass
class Mouvement:
    date: date
    numero_piece: int
    journal_code: str
    libelle: str
    debit: Decimal
    credit: Decimal
    solde: Decimal | None = None  # running balance (relevé / grand livre)


@dataclass
class LigneCompte:
    numero: str
    libelle: str
    montant: Decimal


def resolve_period(
    session: Session,
    association_id: str,
    date_from: date | None,
    date_to: date | None,
) -> tuple[date, date]:
    """Fill missing bounds from the open exercice (else the calendar year)."""
    if date_from and date_to:
        return date_from, date_to
    today = date.today()
    exercice = find_open_exercice(session, association_id, today)
    if exercice is not None:
        return date_from or exercice.date_debut, date_to or exercice.date_fin
    return date_from or date(today.year, 1, 1), date_to or date(today.year, 12, 31)
