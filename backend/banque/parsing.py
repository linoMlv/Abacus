"""Parse a raw bank-statement CSV into signed statement rows.

Pure functions, no I/O and no tenant concern: they turn uploaded text into
``ParsedLigne`` rows a caller persists as ``LigneBancaire``. Every field is
validated and the row count is bounded, so a hostile or malformed upload raises a
clean, user-facing error instead of corrupting an import (zero trust, plan §10).
"""

import csv
import io
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

# A statement never realistically has more rows; this bounds a hostile upload.
MAX_LIGNES = 10_000


class ReleveParseError(ValueError):
    """A statement could not be parsed. The message is user-facing (FR)."""


@dataclass(frozen=True)
class ColumnMapping:
    """Where each field sits in the CSV and how values are formatted.

    Amounts come either as a single **signed** ``montant`` column, or as separate
    ``debit`` (outflow) / ``credit`` (inflow) columns — exactly one of the two
    shapes must be described. Column positions are zero-based indices.
    """

    date: int
    libelle: int
    montant: int | None = None
    debit: int | None = None
    credit: int | None = None
    date_format: str = "%d/%m/%Y"
    decimal_sep: str = ","
    delimiter: str = ";"
    has_header: bool = True


@dataclass(frozen=True)
class ParsedLigne:
    """One statement movement; ``montant`` is signed (>0 inflow, <0 outflow)."""

    date_operation: date
    libelle: str
    montant: Decimal


def parse_releve_csv(content: str, mapping: ColumnMapping) -> list[ParsedLigne]:
    """Parse ``content`` into signed statement rows using ``mapping``.

    Raises :class:`ReleveParseError` on a missing amount description, an
    unreadable field (with the row number) or a statement exceeding
    :data:`MAX_LIGNES` rows.
    """
    if mapping.montant is None and mapping.debit is None and mapping.credit is None:
        raise ReleveParseError("Indiquez une colonne montant, ou débit et crédit.")

    reader = csv.reader(io.StringIO(content), delimiter=mapping.delimiter)
    rows = list(reader)
    start = 1 if mapping.has_header else 0

    parsed: list[ParsedLigne] = []
    for offset, row in enumerate(rows[start:]):
        row_no = start + offset + 1  # 1-based line number, for error messages
        if not any(cell.strip() for cell in row):
            continue  # blank line
        if len(parsed) >= MAX_LIGNES:
            raise ReleveParseError(f"Relevé trop volumineux (max {MAX_LIGNES} lignes).")
        parsed.append(_parse_row(row, mapping, row_no))
    return parsed


def _cell(row: list[str], index: int, row_no: int) -> str:
    if index < 0 or index >= len(row):
        raise ReleveParseError(f"Colonne manquante ligne {row_no}.")
    return row[index].strip()


def _parse_row(row: list[str], mapping: ColumnMapping, row_no: int) -> ParsedLigne:
    raw_date = _cell(row, mapping.date, row_no)
    try:
        jour = datetime.strptime(raw_date, mapping.date_format).date()
    except ValueError:
        raise ReleveParseError(
            f"Date invalide ligne {row_no} : « {raw_date} »."
        ) from None

    libelle = _cell(row, mapping.libelle, row_no)

    if mapping.montant is not None:
        montant = _to_decimal(_cell(row, mapping.montant, row_no), mapping, row_no)
    else:
        credit = (
            _to_decimal(_cell(row, mapping.credit, row_no), mapping, row_no)
            if mapping.credit is not None
            else Decimal("0")
        )
        debit = (
            _to_decimal(_cell(row, mapping.debit, row_no), mapping, row_no)
            if mapping.debit is not None
            else Decimal("0")
        )
        # Credit is an inflow (+), debit an outflow (−); columns hold magnitudes.
        montant = abs(credit) - abs(debit)

    return ParsedLigne(date_operation=jour, libelle=libelle, montant=montant)


def _to_decimal(raw: str, mapping: ColumnMapping, row_no: int) -> Decimal:
    """Signed amount from a locale-formatted cell (empty → 0).

    Strips spaces (incl. NBSP) and thousands separators, honours the mapping's
    decimal separator, and reads a leading ``-`` or surrounding parentheses as
    negative.
    """
    s = raw.replace("\xa0", "").replace(" ", "")
    if not s:
        return Decimal("0")
    negative = s.startswith("-") or (s.startswith("(") and s.endswith(")"))
    kept = "".join(ch for ch in s if ch.isdigit() or ch == mapping.decimal_sep)
    kept = kept.replace(mapping.decimal_sep, ".")
    if not kept or kept == ".":
        raise ReleveParseError(f"Montant invalide ligne {row_no} : « {raw} ».")
    try:
        value = Decimal(kept)
    except InvalidOperation:
        raise ReleveParseError(
            f"Montant invalide ligne {row_no} : « {raw} »."
        ) from None
    return -value if negative else value
