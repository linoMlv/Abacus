"""Closing helpers: per-account soldes, referential lookups and the next year."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlmodel import Session, select

from accounting_engine import CENTS, ZERO, find_exercice_covering, validated_only
from models import (
    Compte,
    Ecriture,
    EcritureStatut,
    Exercice,
    ExerciceStatut,
    LigneEcriture,
)

_JOURNAL_CLOTURE = "OD"  # opérations diverses
# Result accounts: excédent (120) / déficit (129) and their affectation targets.
_COMPTE_EXCEDENT = "120"
_COMPTE_DEFICIT = "129"
_REPORT_EXCEDENT = "110"  # report à nouveau créditeur
_REPORT_DEFICIT = "119"  # report à nouveau débiteur
_RESERVES = "106"


def _bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def _account_soldes(
    session: Session, association_id: str, exercice_id: str, classes: list[int]
) -> list[tuple[str, Decimal]]:
    """Per-account solde (Σdébit − Σcrédit) within an exercice, validated only."""
    debit = func.coalesce(func.sum(LigneEcriture.debit), 0)
    credit = func.coalesce(func.sum(LigneEcriture.credit), 0)
    rows = session.exec(
        select(Compte.id, Compte.numero, debit, credit)
        .select_from(LigneEcriture)
        .join(Ecriture, Ecriture.id == LigneEcriture.ecriture_id)
        .join(Compte, Compte.id == LigneEcriture.compte_id)
        .where(
            Ecriture.association_id == association_id,
            Compte.association_id == association_id,
            Ecriture.exercice_id == exercice_id,
            Compte.classe.in_(classes),
            validated_only(),
        )
        .group_by(Compte.id, Compte.numero)
    ).all()
    result: list[tuple[str, Decimal]] = []
    for compte_id, numero, d, c in rows:
        # The result account (12) is not a carried-forward balance: it is
        # affected explicitly, so keep it out of the report à nouveau.
        if numero.startswith("12"):
            continue
        solde = (Decimal(str(d)) - Decimal(str(c))).quantize(CENTS)
        if solde != ZERO:
            result.append((compte_id, solde))
    return result


def _resolve_compte(session: Session, association_id: str, numero: str) -> Compte:
    compte = session.exec(
        select(Compte).where(
            Compte.association_id == association_id, Compte.numero == numero
        )
    ).first()
    if compte is None:
        raise _bad_request(f"Référentiel comptable incomplet (compte {numero} absent).")
    return compte


def _next_period(prev: Exercice) -> tuple[date, date, str]:
    """Default period for the year following ``prev``: the day after it ends,
    spanning one year (same anniversary), with a civil or straddling label."""
    debut = prev.date_fin + timedelta(days=1)
    try:
        fin = debut.replace(year=debut.year + 1) - timedelta(days=1)
    except ValueError:  # 29 Feb -> the next year has no 29 Feb
        fin = date(debut.year + 1, 3, 1) - timedelta(days=1)
    libelle = str(debut.year) if debut.year == fin.year else f"{debut.year}-{fin.year}"
    return debut, fin, libelle


def _resolve_next_exercice(
    session: Session, association_id: str, prev: Exercice
) -> Exercice:
    """The fiscal year following ``prev``: an existing one, else created."""
    next_debut = prev.date_fin + timedelta(days=1)
    suivant = find_exercice_covering(session, association_id, next_debut)
    if suivant is not None:
        if suivant.statut == ExerciceStatut.CLOTURE:
            raise _bad_request("L'exercice suivant est déjà clôturé.")
        return suivant

    debut, fin, libelle = _next_period(prev)
    overlap = session.exec(
        select(Exercice.id).where(
            Exercice.association_id == association_id,
            Exercice.date_debut <= fin,
            Exercice.date_fin >= debut,
        )
    ).first()
    if overlap is not None:
        raise _bad_request(
            "Impossible de créer l'exercice suivant (chevauchement) — "
            "créez-le manuellement."
        )
    suivant = Exercice(
        association_id=association_id,
        libelle=libelle,
        date_debut=debut,
        date_fin=fin,
    )
    session.add(suivant)
    session.flush()  # need its id for the report à nouveau entry
    return suivant


def _validate_now(ecriture: Ecriture, user_id: str) -> None:
    """Stamp a generated closing entry as validated (official, immutable)."""
    ecriture.statut = EcritureStatut.VALIDEE
    ecriture.validated_by = user_id
    ecriture.validated_at = datetime.now(UTC)
