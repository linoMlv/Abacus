"""Parse an OFX bank statement into signed statement rows.

OFX is self-describing (no column mapping): each ``STMTTRN`` carries a date, a
signed amount, a label and a unique ``FITID``. Both flavours are handled by
``ofxparse`` — 1.x (SGML, most French banks) and 2.x (XML). The FITID rides along
on :class:`ParsedLigne` so the caller can skip a movement already imported.
"""

import io
from decimal import Decimal

from ofxparse import OfxParser

from .parsing import ParsedLigne, ReleveParseError

_CENTS = Decimal("0.01")
_MAX_LABEL = 255


def parse_releve_ofx(content: bytes) -> list[ParsedLigne]:
    """Parse OFX ``content`` (raw bytes) into signed statement rows.

    Raises :class:`ReleveParseError` on an unreadable file or one with no
    transaction.
    """
    try:
        ofx = OfxParser.parse(io.BytesIO(content))
    except Exception as exc:  # ofxparse raises a variety of parse errors
        raise ReleveParseError("Fichier OFX illisible ou invalide.") from exc

    lignes: list[ParsedLigne] = []
    for account in getattr(ofx, "accounts", None) or []:
        statement = getattr(account, "statement", None)
        if statement is None:
            continue
        for txn in statement.transactions:
            lignes.append(_to_ligne(txn))

    if not lignes:
        raise ReleveParseError("Aucune opération trouvée dans le fichier OFX.")
    return lignes


def _to_ligne(txn) -> ParsedLigne:
    # NAME + MEMO make the human label; some banks fill only one of the two.
    parts = [
        (getattr(txn, "payee", "") or "").strip(),
        (getattr(txn, "memo", "") or "").strip(),
    ]
    libelle = " ".join(p for p in parts if p)[:_MAX_LABEL] or "Opération"
    jour = txn.date.date() if hasattr(txn.date, "date") else txn.date
    return ParsedLigne(
        date_operation=jour,
        libelle=libelle,
        montant=Decimal(txn.amount).quantize(_CENTS),
        fitid=(txn.id or None),
    )
