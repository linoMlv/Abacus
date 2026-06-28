"""Dashboard synthesis (T6): period analytics + current alerts in one read.

A single tenant-scoped, read-only endpoint that powers the Synthèse page:

* **résultat** of the period — produits (class 7) − charges (class 6),
* **répartition** of the period by category and by event,
* **courbe de trésorerie** — opening balance carried into the period, then the
  cumulative end-of-day balance of the treasury accounts (class 5 named),
* **alertes** — current state, independent of the period: drafts to validate,
  active events over their dépenses budget, and open fiscal years past due.

Reading is open to any active member; every aggregate is filtered on the
server-resolved ``association_id`` (an id from the client never widens access).
"""

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlmodel import Session, asc, select

from accounting_engine import find_open_exercice
from auth_context import AccessContext, get_active_membership
from database import get_session
from models import (
    AlerteEvenement,
    AlerteExercice,
    CategorieSaisie,
    Compte,
    CourbePoint,
    Ecriture,
    EcritureStatut,
    Evenement,
    EvenementStatut,
    Exercice,
    ExerciceStatut,
    LigneEcriture,
    RepartitionCategorieItem,
    RepartitionEvenementItem,
    SyntheseAlertes,
    SyntheseRead,
    SyntheseResultat,
)

router = APIRouter(prefix="/api/asso/{association_id}", tags=["synthese"])

CENTS = Decimal("0.01")
ZERO = Decimal("0.00")
# Income-statement classes: charges (6) and produits (7).
_CHARGE, _PRODUIT = 6, 7


def _dec(value) -> Decimal:
    """SQL SUM/COALESCE comes back as a string or int depending on the driver."""
    return Decimal(str(value))


def _default_range(session: Session, association_id: str) -> tuple[date, date]:
    """Default period: the open fiscal year covering today, else the calendar year."""
    today = date.today()
    exercice = find_open_exercice(session, association_id, today)
    if exercice is not None:
        return exercice.date_debut, exercice.date_fin
    return date(today.year, 1, 1), date(today.year, 12, 31)


def _resultat(
    session: Session, association_id: str, date_from: date, date_to: date
) -> SyntheseResultat:
    rows = session.exec(
        select(
            Compte.classe,
            func.coalesce(func.sum(LigneEcriture.debit), 0),
            func.coalesce(func.sum(LigneEcriture.credit), 0),
        )
        .select_from(LigneEcriture)
        .join(Ecriture, Ecriture.id == LigneEcriture.ecriture_id)
        .join(Compte, Compte.id == LigneEcriture.compte_id)
        .where(
            Ecriture.association_id == association_id,
            Compte.association_id == association_id,
            Ecriture.date >= date_from,
            Ecriture.date <= date_to,
            Compte.classe.in_([_CHARGE, _PRODUIT]),
        )
        .group_by(Compte.classe)
    ).all()

    recettes, depenses = ZERO, ZERO
    for classe, total_debit, total_credit in rows:
        debit, credit = _dec(total_debit), _dec(total_credit)
        if classe == _PRODUIT:
            recettes += credit - debit
        else:
            depenses += debit - credit
    recettes, depenses = recettes.quantize(CENTS), depenses.quantize(CENTS)
    return SyntheseResultat(
        recettes=recettes, depenses=depenses, resultat=recettes - depenses
    )


def _repartition_categories(
    session: Session, association_id: str, date_from: date, date_to: date
) -> list[RepartitionCategorieItem]:
    """Per category, the magnitude booked on its produit/charge line over the period."""
    rows = session.exec(
        select(
            CategorieSaisie.id,
            CategorieSaisie.libelle,
            CategorieSaisie.sens,
            func.coalesce(func.sum(LigneEcriture.debit + LigneEcriture.credit), 0),
        )
        .select_from(Ecriture)
        .join(CategorieSaisie, CategorieSaisie.id == Ecriture.categorie_id)
        .join(LigneEcriture, LigneEcriture.ecriture_id == Ecriture.id)
        .join(Compte, Compte.id == LigneEcriture.compte_id)
        .where(
            Ecriture.association_id == association_id,
            CategorieSaisie.association_id == association_id,
            Ecriture.date >= date_from,
            Ecriture.date <= date_to,
            Compte.classe.in_([_CHARGE, _PRODUIT]),
        )
        .group_by(CategorieSaisie.id, CategorieSaisie.libelle, CategorieSaisie.sens)
    ).all()

    items = [
        RepartitionCategorieItem(
            categorie_id=cid,
            libelle=libelle,
            sens=sens,
            montant=_dec(montant).quantize(CENTS),
        )
        for cid, libelle, sens, montant in rows
    ]
    items.sort(key=lambda i: i.montant, reverse=True)
    return items


def _repartition_evenements(
    session: Session, association_id: str, date_from: date, date_to: date
) -> list[RepartitionEvenementItem]:
    rows = session.exec(
        select(
            Ecriture.evenement_id,
            Compte.classe,
            func.coalesce(func.sum(LigneEcriture.debit), 0),
            func.coalesce(func.sum(LigneEcriture.credit), 0),
        )
        .select_from(Ecriture)
        .join(LigneEcriture, LigneEcriture.ecriture_id == Ecriture.id)
        .join(Compte, Compte.id == LigneEcriture.compte_id)
        .where(
            Ecriture.association_id == association_id,
            Ecriture.evenement_id.is_not(None),
            Ecriture.date >= date_from,
            Ecriture.date <= date_to,
            Compte.classe.in_([_CHARGE, _PRODUIT]),
        )
        .group_by(Ecriture.evenement_id, Compte.classe)
    ).all()

    agg: dict[str, list[Decimal]] = {}
    for evenement_id, classe, total_debit, total_credit in rows:
        debit, credit = _dec(total_debit), _dec(total_credit)
        acc = agg.setdefault(evenement_id, [ZERO, ZERO])
        if classe == _PRODUIT:
            acc[0] += credit - debit
        else:
            acc[1] += debit - credit

    evenements = {
        e.id: e
        for e in session.exec(
            select(Evenement).where(Evenement.association_id == association_id)
        ).all()
    }
    items: list[RepartitionEvenementItem] = []
    for evenement_id, (recettes, depenses) in agg.items():
        evenement = evenements.get(evenement_id)
        if evenement is None:  # defensive: a tag must resolve within the tenant
            continue
        recettes, depenses = recettes.quantize(CENTS), depenses.quantize(CENTS)
        items.append(
            RepartitionEvenementItem(
                evenement_id=evenement_id,
                nom=evenement.nom,
                couleur=evenement.couleur,
                recettes=recettes,
                depenses=depenses,
                resultat=recettes - depenses,
            )
        )
    items.sort(key=lambda i: i.nom)
    return items


def _courbe_tresorerie(
    session: Session, association_id: str, date_from: date, date_to: date
) -> list[CourbePoint]:
    """Treasury balance over the period: opening carried in, then cumulative per day."""
    treasury_ids = session.exec(
        select(Compte.id).where(
            Compte.association_id == association_id,
            Compte.type_tresorerie.is_not(None),
        )
    ).all()
    if not treasury_ids:
        return []

    opening_debit, opening_credit = session.exec(
        select(
            func.coalesce(func.sum(LigneEcriture.debit), 0),
            func.coalesce(func.sum(LigneEcriture.credit), 0),
        )
        .select_from(LigneEcriture)
        .join(Ecriture, Ecriture.id == LigneEcriture.ecriture_id)
        .where(
            Ecriture.association_id == association_id,
            LigneEcriture.compte_id.in_(treasury_ids),
            Ecriture.date < date_from,
        )
    ).one()
    opening = _dec(opening_debit) - _dec(opening_credit)

    daily = session.exec(
        select(
            Ecriture.date,
            func.coalesce(func.sum(LigneEcriture.debit), 0),
            func.coalesce(func.sum(LigneEcriture.credit), 0),
        )
        .select_from(Ecriture)
        .join(LigneEcriture, LigneEcriture.ecriture_id == Ecriture.id)
        .where(
            Ecriture.association_id == association_id,
            LigneEcriture.compte_id.in_(treasury_ids),
            Ecriture.date >= date_from,
            Ecriture.date <= date_to,
        )
        .group_by(Ecriture.date)
    ).all()
    nets = {jour: _dec(debit) - _dec(credit) for jour, debit, credit in daily}

    # Nothing happened up to or during the period: no curve to draw.
    if not nets and opening == ZERO:
        return []

    running = opening
    points: list[CourbePoint] = []
    for jour in sorted(set(nets) | {date_from}):  # anchor the start of the period
        running += nets.get(jour, ZERO)
        points.append(CourbePoint(date=jour, solde=running.quantize(CENTS)))
    return points


def _alertes(session: Session, association_id: str) -> SyntheseAlertes:
    brouillons = session.exec(
        select(func.count())
        .select_from(Ecriture)
        .where(
            Ecriture.association_id == association_id,
            Ecriture.statut == EcritureStatut.BROUILLON,
        )
    ).one()

    # Active events whose all-time dépenses exceed their budget.
    realise_rows = session.exec(
        select(
            Ecriture.evenement_id,
            func.coalesce(func.sum(LigneEcriture.debit), 0),
            func.coalesce(func.sum(LigneEcriture.credit), 0),
        )
        .select_from(Ecriture)
        .join(LigneEcriture, LigneEcriture.ecriture_id == Ecriture.id)
        .join(Compte, Compte.id == LigneEcriture.compte_id)
        .where(
            Ecriture.association_id == association_id,
            Ecriture.evenement_id.is_not(None),
            Compte.classe == _CHARGE,
        )
        .group_by(Ecriture.evenement_id)
    ).all()
    realise = {eid: _dec(d) - _dec(c) for eid, d, c in realise_rows}
    evenements_depasses: list[AlerteEvenement] = []
    over_budget = session.exec(
        select(Evenement).where(
            Evenement.association_id == association_id,
            Evenement.statut == EvenementStatut.ACTIF,
            Evenement.budget_depenses.is_not(None),
        )
    ).all()
    for evenement in over_budget:
        depenses = realise.get(evenement.id, ZERO).quantize(CENTS)
        if depenses > evenement.budget_depenses:
            evenements_depasses.append(
                AlerteEvenement(
                    evenement_id=evenement.id,
                    nom=evenement.nom,
                    budget_depenses=evenement.budget_depenses.quantize(CENTS),
                    realise_depenses=depenses,
                )
            )
    evenements_depasses.sort(key=lambda a: a.nom)

    today = date.today()
    exercices_a_cloturer = [
        AlerteExercice(
            exercice_id=exercice.id,
            libelle=exercice.libelle,
            date_fin=exercice.date_fin,
        )
        for exercice in session.exec(
            select(Exercice)
            .where(
                Exercice.association_id == association_id,
                Exercice.statut == ExerciceStatut.OUVERT,
                Exercice.date_fin < today,
            )
            .order_by(asc(Exercice.date_fin))
        ).all()
    ]

    return SyntheseAlertes(
        brouillons=brouillons,
        evenements_depasses=evenements_depasses,
        exercices_a_cloturer=exercices_a_cloturer,
    )


@router.get("/synthese", response_model=SyntheseRead)
def get_synthese(
    date_from: date | None = None,
    date_to: date | None = None,
    ctx: AccessContext = Depends(get_active_membership),
    session: Session = Depends(get_session),
):
    """Consolidated dashboard for the active association over an optional period.

    With no dates, the period defaults to the open fiscal year (else the calendar
    year). Treasury balances and alerts are read separately; everything here is
    re-derived from the ledger, scoped to ``ctx.association_id``.
    """
    default_from, default_to = _default_range(session, ctx.association_id)
    date_from = date_from or default_from
    date_to = date_to or default_to
    aid = ctx.association_id

    return SyntheseRead(
        date_from=date_from,
        date_to=date_to,
        resultat=_resultat(session, aid, date_from, date_to),
        repartition_categories=_repartition_categories(
            session, aid, date_from, date_to
        ),
        repartition_evenements=_repartition_evenements(
            session, aid, date_from, date_to
        ),
        courbe_tresorerie=_courbe_tresorerie(session, aid, date_from, date_to),
        alertes=_alertes(session, aid),
    )
