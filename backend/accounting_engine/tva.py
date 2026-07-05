"""VAT arithmetic (pure).

Associations enter amounts **TTC** (tax included, plan §4); the engine extracts
the HT base and the VAT so the two always reconstitute the TTC exactly — the VAT
is taken as ``TTC - HT`` rather than computed independently, which guarantees the
entry stays balanced with no rounding drift.
"""

from decimal import Decimal

from .constants import CENTS, ZERO
from .invariants import EntryError

# France's VAT rates live in [0, 100); a rate outside that is a client error.
_HUNDRED = Decimal(100)


def split_ttc(ttc: Decimal, taux: Decimal) -> tuple[Decimal, Decimal]:
    """Split a TTC amount at ``taux`` percent into ``(ht, tva)``.

    ``ht`` is rounded to the cent and ``tva = ttc - ht``, so ``ht + tva == ttc``
    exactly. A zero rate yields ``(ttc, 0)``.
    """
    if taux < ZERO or taux >= _HUNDRED:
        raise EntryError("Le taux de TVA doit être compris entre 0 et 100.")
    if taux == ZERO:
        return ttc.quantize(CENTS), ZERO
    ht = (ttc / (Decimal(1) + taux / _HUNDRED)).quantize(CENTS)
    tva = (ttc - ht).quantize(CENTS)
    return ht, tva
