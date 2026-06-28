"""Locale-aware formatting for exported documents (fr-FR)."""

from datetime import date
from decimal import Decimal

CENTS = Decimal("0.01")
# Narrow-ish grouping: a non-breaking space (present in IBM Plex / cp1252).
_NBSP = " "


def to_decimal(value) -> Decimal:
    if value is None:
        return Decimal("0.00")
    return Decimal(str(value)).quantize(CENTS)


def fmt_amount(value) -> str:
    """ "1 234,56" — grouped thousands, comma decimal, two decimals."""
    d = to_decimal(value)
    grouped = f"{abs(d):,.2f}".replace(",", _NBSP).replace(".", ",")
    return f"-{grouped}" if d < 0 else grouped


def fmt_eur(value) -> str:
    """ "1 234,56 €"."""
    return f"{fmt_amount(value)}{_NBSP}€"


def fmt_date(value: date | None) -> str:
    """ "29/06/2026" from a date, or "" when absent."""
    return value.strftime("%d/%m/%Y") if value else ""
