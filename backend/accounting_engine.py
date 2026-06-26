"""Double-entry engine: the invariants that keep every entry balanced.

This commit exposes the core balance invariant (Σ débit = Σ crédit). The
simple→double-entry posting engine and the gapless voucher numbering build on
this guarantee in later commits.

The invariant is intentionally pure (no I/O, no session): it can be unit-tested
in isolation and reused by every write path (simple entry, manual entry,
import, recurrence) so no entry can ever be persisted unbalanced.
"""

from collections.abc import Sequence
from datetime import date
from decimal import Decimal

from sqlalchemy import func
from sqlmodel import Session, select

from models import (
    Ecriture,
    EcritureOrigine,
    LigneEcriture,
    SensCategorie,
)

CENTS = Decimal("0.01")
ZERO = Decimal("0.00")


class EntryError(ValueError):
    """A double-entry invariant was violated. Message is user-facing (FR)."""


def validate_lignes(lignes: Sequence[LigneEcriture]) -> None:
    """Ensure ``lignes`` form a valid, balanced accounting entry.

    Rules enforced:

    * at least two lines (an entry moves value between accounts);
    * every line carries a non-negative amount on exactly one side
      (debit xor credit, strictly positive);
    * Σ débit = Σ crédit, and the total is strictly positive.

    Raises :class:`EntryError` (with a French message) on the first violation.
    """
    if len(lignes) < 2:
        raise EntryError("Une écriture comptable doit comporter au moins deux lignes.")

    total_debit = ZERO
    total_credit = ZERO
    for ligne in lignes:
        debit = _as_amount(ligne.debit, "débit")
        credit = _as_amount(ligne.credit, "crédit")
        if debit > ZERO and credit > ZERO:
            raise EntryError(
                "Une ligne ne peut porter à la fois un débit et un crédit."
            )
        if debit == ZERO and credit == ZERO:
            raise EntryError("Une ligne doit porter un montant au débit ou au crédit.")
        total_debit += debit
        total_credit += credit

    if total_debit != total_credit:
        raise EntryError(
            f"Écriture déséquilibrée : débit {total_debit} ≠ crédit {total_credit}."
        )
    if total_debit == ZERO:
        raise EntryError(
            "Le montant total de l'écriture doit être strictement positif."
        )


def _as_amount(value: Decimal | int | str, side: str) -> Decimal:
    """Coerce an amount to a non-negative 2-decimal :class:`Decimal`."""
    amount = Decimal(value).quantize(CENTS)
    if amount < ZERO:
        raise EntryError(f"Le montant au {side} ne peut pas être négatif.")
    return amount


def next_numero_piece(session: Session, association_id: str) -> int:
    """Return the next sequential voucher number for ``association_id``.

    Numbering is per association and continuous (``max + 1``). The
    ``(association_id, numero_piece)`` unique constraint guards against a
    concurrent collision (one writer fails and retries).
    """
    current_max = session.exec(
        select(func.max(Ecriture.numero_piece)).where(
            Ecriture.association_id == association_id
        )
    ).one()
    return (current_max or 0) + 1


def build_ecriture_simple(
    *,
    association_id: str,
    exercice_id: str,
    journal_id: str,
    compte_tresorerie_id: str,
    compte_categorie_id: str,
    sens: SensCategorie,
    montant: Decimal | int | str,
    date_ecriture: date,
    libelle: str,
    numero_piece: int,
    created_by: str | None = None,
    origine: EcritureOrigine = EcritureOrigine.SAISIE_SIMPLE,
) -> Ecriture:
    """Turn a plain recette/dépense into a balanced two-line entry.

    * **Recette** — money in: D cash account / C produit account.
    * **Dépense** — money out: D charge account / C cash account.

    The category supplies the produit/charge account
    (``compte_categorie_id``); the cash account (``compte_tresorerie_id``,
    512/531) is the one the money actually moved on. The result is validated
    against the balance invariant before being returned (unsaved, so the caller
    owns the transaction).
    """
    montant = _as_amount(montant, "montant")
    if montant == ZERO:
        raise EntryError("Le montant doit être strictement positif.")

    if sens == SensCategorie.RECETTE:
        debit_compte, credit_compte = compte_tresorerie_id, compte_categorie_id
    else:
        debit_compte, credit_compte = compte_categorie_id, compte_tresorerie_id

    lignes = [
        LigneEcriture(compte_id=debit_compte, libelle=libelle, debit=montant),
        LigneEcriture(compte_id=credit_compte, libelle=libelle, credit=montant),
    ]
    validate_lignes(lignes)

    return Ecriture(
        association_id=association_id,
        exercice_id=exercice_id,
        journal_id=journal_id,
        date=date_ecriture,
        numero_piece=numero_piece,
        libelle=libelle,
        origine=origine,
        created_by=created_by,
        lignes=lignes,
    )
