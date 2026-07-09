"""Annexe (ANC): computed tables data gathering."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import func
from sqlmodel import Session, asc, select

from accounting_engine import ZERO, scope_exercice, validated_only
from models import AnnexeRubrique, Compte, CompteType, Ecriture, LigneEcriture

from .common import LigneCompte, _dec

# Which annexe table an account belongs to, and its ordered title.
_ANNEXE_SECTIONS = [
    "Fonds dédiés",
    "Contributions volontaires en nature",
    "Immobilisations et amortissements",
    "Fonds propres",
]


@dataclass
class AnnexeSection:
    titre: str
    lignes: list[LigneCompte]
    total: Decimal


@dataclass
class AnnexeNarrative:
    titre: str
    contenu: str


@dataclass
class AnnexeData:
    date_to: date
    narrative: list[AnnexeNarrative]
    sections: list[AnnexeSection]


def _annexe_bucket(numero: str, classe: int) -> str | None:
    if numero.startswith("19") or numero in ("689", "789"):
        return "Fonds dédiés"
    if classe == 8:
        return "Contributions volontaires en nature"
    if classe == 2:
        return "Immobilisations et amortissements"
    if numero[:2] in ("10", "11", "12"):
        return "Fonds propres"
    return None


def annexe_data(session: Session, association_id: str, date_to: date) -> AnnexeData:
    """Computed annexe tables at ``date_to``, scoped to the covering exercice.

    Each account is shown with its *natural* balance (debit balance for
    actif/charge, credit balance for passif/produit — always a positive amount),
    bucketed into the ANC annexe tables: fonds dédiés (19x, 689/789),
    contributions volontaires en nature (class 8), immobilisations et
    amortissements (class 2) and fonds propres (10/11/12).
    """
    exercice = scope_exercice(session, association_id, date_to)
    exercice_id = exercice.id if exercice is not None else None

    stmt = (
        select(
            Compte.numero,
            Compte.libelle,
            Compte.classe,
            Compte.type,
            func.coalesce(func.sum(LigneEcriture.debit), 0),
            func.coalesce(func.sum(LigneEcriture.credit), 0),
        )
        .select_from(LigneEcriture)
        .join(Ecriture, Ecriture.id == LigneEcriture.ecriture_id)
        .join(Compte, Compte.id == LigneEcriture.compte_id)
        .where(
            Ecriture.association_id == association_id,
            Compte.association_id == association_id,
            Ecriture.date <= date_to,
            validated_only(),
        )
        .group_by(Compte.numero, Compte.libelle, Compte.classe, Compte.type)
        .order_by(asc(Compte.numero))
    )
    if exercice_id is not None:
        stmt = stmt.where(Ecriture.exercice_id == exercice_id)

    buckets: dict[str, list[LigneCompte]] = {titre: [] for titre in _ANNEXE_SECTIONS}
    totals: dict[str, Decimal] = {titre: ZERO for titre in _ANNEXE_SECTIONS}
    for numero, libelle, classe, ctype, debit, credit in session.exec(stmt).all():
        titre = _annexe_bucket(numero, classe)
        if titre is None:
            continue
        if ctype in (CompteType.ACTIF, CompteType.CHARGE):
            montant = _dec(debit) - _dec(credit)
        else:
            montant = _dec(credit) - _dec(debit)
        if montant == ZERO:
            continue
        buckets[titre].append(LigneCompte(numero, libelle, montant))
        totals[titre] += montant

    sections = [
        AnnexeSection(titre=titre, lignes=buckets[titre], total=totals[titre])
        for titre in _ANNEXE_SECTIONS
    ]
    return AnnexeData(
        date_to=date_to,
        narrative=_narrative(session, association_id, exercice_id),
        sections=sections,
    )


def _narrative(
    session: Session, association_id: str, exercice_id: str | None
) -> list[AnnexeNarrative]:
    """Filled-in narrative rubrics of the covering exercice, in display order.

    Empty rubrics (title only, no body) are skipped so the document shows only
    what the association actually wrote.
    """
    if exercice_id is None:
        return []
    rows = session.exec(
        select(AnnexeRubrique)
        .where(
            AnnexeRubrique.association_id == association_id,
            AnnexeRubrique.exercice_id == exercice_id,
        )
        .order_by(asc(AnnexeRubrique.ordre), asc(AnnexeRubrique.titre))
    ).all()
    return [
        AnnexeNarrative(titre=r.titre, contenu=r.contenu.strip())
        for r in rows
        if r.contenu.strip()
    ]
