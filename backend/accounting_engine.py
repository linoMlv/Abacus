"""Double-entry engine: the invariants that keep every entry balanced.

This commit exposes the core balance invariant (Σ débit = Σ crédit). The
simple→double-entry posting engine and the gapless voucher numbering build on
this guarantee in later commits.

The invariant is intentionally pure (no I/O, no session): it can be unit-tested
in isolation and reused by every write path (simple entry, manual entry,
import, recurrence) so no entry can ever be persisted unbalanced.
"""

from collections.abc import Sequence
from decimal import Decimal

from models import LigneEcriture

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
