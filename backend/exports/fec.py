"""FEC export — Fichier des Écritures Comptables (arrêté du 29 juillet 2013).

A flat, tab-separated text file with the 18 regulatory columns, one row per
accounting line, for a single fiscal year and validated entries only (the FEC is
the definitive accounting record — drafts are not part of it). Amounts use the
French decimal comma; dates are ``AAAAMMJJ``.
"""

from datetime import date
from decimal import Decimal

from sqlmodel import Session, asc, select

from accounting_engine import validated_only
from models import Compte, Ecriture, Journal, LigneEcriture

FEC_MEDIA_TYPE = "text/plain; charset=utf-8"

# The 18 columns in their regulatory order.
FEC_HEADER = [
    "JournalCode",
    "JournalLib",
    "EcritureNum",
    "EcritureDate",
    "CompteNum",
    "CompteLib",
    "CompAuxNum",
    "CompAuxLib",
    "PieceRef",
    "PieceDate",
    "EcritureLib",
    "Debit",
    "Credit",
    "EcritureLet",
    "DateLet",
    "ValidDate",
    "Montantdevise",
    "Idevise",
]


def _fmt_date(value: date | None) -> str:
    return value.strftime("%Y%m%d") if value is not None else ""


def _fmt_amount(value: Decimal) -> str:
    return f"{value:.2f}".replace(".", ",")


def _sanitize(value: str | None) -> str:
    """Keep the tab/newline field and record separators unambiguous."""
    if not value:
        return ""
    return value.replace("\t", " ").replace("\r", " ").replace("\n", " ")


def build_fec(session: Session, association_id: str, exercice_id: str) -> bytes:
    """Render the FEC of one fiscal year as UTF-8 bytes (tenant-scoped)."""
    rows = session.exec(
        select(LigneEcriture, Ecriture, Compte, Journal)
        .join(Ecriture, Ecriture.id == LigneEcriture.ecriture_id)
        .join(Compte, Compte.id == LigneEcriture.compte_id)
        .join(Journal, Journal.id == Ecriture.journal_id)
        .where(
            Ecriture.association_id == association_id,
            Ecriture.exercice_id == exercice_id,
            validated_only(),
        )
        .order_by(asc(Ecriture.date), asc(Ecriture.numero_piece), asc(LigneEcriture.id))
    ).all()

    lines = ["\t".join(FEC_HEADER)]
    for ligne, ecriture, compte, journal in rows:
        piece_ref = ecriture.reference_externe or str(ecriture.numero_piece)
        champs = [
            journal.code,
            journal.libelle,
            str(ecriture.numero_piece),
            _fmt_date(ecriture.date),
            compte.numero,
            compte.libelle,
            "",  # CompAuxNum — auxiliary accounting not used
            "",  # CompAuxLib
            piece_ref,
            _fmt_date(ecriture.date),  # PieceDate
            ligne.libelle or ecriture.libelle,
            _fmt_amount(ligne.debit),
            _fmt_amount(ligne.credit),
            "",  # EcritureLet — lettrage not used yet
            "",  # DateLet
            _fmt_date(ecriture.validated_at.date() if ecriture.validated_at else None),
            "",  # Montantdevise
            "",  # Idevise
        ]
        lines.append("\t".join(_sanitize(c) for c in champs))

    return ("\n".join(lines) + "\n").encode("utf-8")
