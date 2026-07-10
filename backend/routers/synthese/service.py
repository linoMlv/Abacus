"""Read-only computation for the dashboard synthesis.

Every aggregate is filtered on the server-resolved ``association_id`` (an id
from the client never widens access) and on validated entries only.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import func
from sqlmodel import Session, asc, select

from accounting_engine import (
    CENTS,
    CLASSE_CHARGE,
    CLASSE_PRODUIT,
    CLASSES_GESTION,
    ZERO,
    exclude_cloture,
    find_open_exercice,
    scope_exercice,
    to_decimal,
    validated_only,
)
from budget_engine import (
    BudgetLigneView,
    build_budget_view,
    load_prevu,
    overruns,
    realise_par_categorie,
)
from models import (
    AlerteBudget,
    AlerteEvenement,
    AlerteExercice,
    BudgetSynthese,
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
    SyntheseResultat,
)

# Income-statement classes: charges (6) and produits (7).
_CHARGE, _PRODUIT = CLASSE_CHARGE, CLASSE_PRODUIT
_dec = to_decimal


def _signed(classe: int, debit: Decimal, credit: Decimal) -> tuple[Decimal, Decimal]:
    """The (recette, dépense) contribution of one class-6/7 aggregate line.

    A produit (class 7) reads as a recette (crédit − débit); a charge (class 6)
    as a dépense (débit − crédit). Centralises the sign convention shared by the
    résultat and the per-event répartition.
    """
    if classe == _PRODUIT:
        return credit - debit, ZERO
    return ZERO, debit - credit


def default_range(session: Session, association_id: str) -> tuple[date, date]:
    """Default period: the open fiscal year covering today, else the calendar year."""
    today = date.today()
    exercice = find_open_exercice(session, association_id, today)
    if exercice is not None:
        return exercice.date_debut, exercice.date_fin
    return date(today.year, 1, 1), date(today.year, 12, 31)


def resultat(
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
            Compte.classe.in_(CLASSES_GESTION),
            validated_only(),
            exclude_cloture(),
        )
        .group_by(Compte.classe)
    ).all()

    recettes, depenses = ZERO, ZERO
    for classe, total_debit, total_credit in rows:
        recette, depense = _signed(classe, _dec(total_debit), _dec(total_credit))
        recettes += recette
        depenses += depense
    recettes, depenses = recettes.quantize(CENTS), depenses.quantize(CENTS)
    return SyntheseResultat(
        recettes=recettes, depenses=depenses, resultat=recettes - depenses
    )


def repartition_categories(
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
            Compte.classe.in_(CLASSES_GESTION),
            validated_only(),
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


def repartition_evenements(
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
            Compte.classe.in_(CLASSES_GESTION),
            validated_only(),
        )
        .group_by(Ecriture.evenement_id, Compte.classe)
    ).all()

    agg: dict[str, list[Decimal]] = {}
    for evenement_id, classe, total_debit, total_credit in rows:
        recette, depense = _signed(classe, _dec(total_debit), _dec(total_credit))
        acc = agg.setdefault(evenement_id, [ZERO, ZERO])
        acc[0] += recette
        acc[1] += depense

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


def courbe_tresorerie(
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

    # Scope to the exercice of the period start: its report à nouveau is the
    # opening, so prior years' movements must not be counted again (they were
    # already summed into the report). A no-op before any closing (one exercice).
    exercice = scope_exercice(session, association_id, date_from)
    exercice_id = exercice.id if exercice is not None else None

    opening_stmt = (
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
            validated_only(),
        )
    )
    daily_stmt = (
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
            validated_only(),
        )
        .group_by(Ecriture.date)
    )
    if exercice_id is not None:
        opening_stmt = opening_stmt.where(Ecriture.exercice_id == exercice_id)
        daily_stmt = daily_stmt.where(Ecriture.exercice_id == exercice_id)

    opening_debit, opening_credit = session.exec(opening_stmt).one()
    opening = _dec(opening_debit) - _dec(opening_credit)

    daily = session.exec(daily_stmt).all()
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


def _active_categories(session: Session, association_id: str) -> list[CategorieSaisie]:
    return session.exec(
        select(CategorieSaisie).where(
            CategorieSaisie.association_id == association_id,
            CategorieSaisie.is_active.is_(True),
        )
    ).all()


def _to_alerte_budget(ligne: BudgetLigneView) -> AlerteBudget:
    return AlerteBudget(
        categorie_id=ligne.categorie_id,
        libelle=ligne.libelle,
        montant_prevu=ligne.montant_prevu,
        realise=ligne.realise,
    )


def _budget_view_for(session: Session, association_id: str, exercice_id: str):
    """The budget view of an exercice, or ``None`` when no budget amount is set."""
    prevu = load_prevu(session, association_id, exercice_id)
    if not prevu:
        return None
    categories = _active_categories(session, association_id)
    realise = realise_par_categorie(session, association_id, exercice_id)
    return build_budget_view(categories, prevu, realise)


def budget_synthese(
    session: Session, association_id: str, date_from: date
) -> BudgetSynthese | None:
    """Widget: prévu vs réalisé of the budget for the exercice covering the period.

    The budget is annual, so the réalisé spans the whole covering exercice (not the
    selected sub-period). ``None`` when that exercice has no budget defined.
    """
    exercice = scope_exercice(session, association_id, date_from)
    if exercice is None:
        return None
    view = _budget_view_for(session, association_id, exercice.id)
    if view is None:
        return None
    return BudgetSynthese(
        exercice_id=exercice.id,
        exercice_libelle=exercice.libelle,
        recettes_prevu=view.total_recettes_prevu,
        recettes_realise=view.total_recettes_realise,
        depenses_prevu=view.total_depenses_prevu,
        depenses_realise=view.total_depenses_realise,
        resultat_prevu=view.resultat_prevu,
        resultat_realise=view.resultat_realise,
        depassements=[_to_alerte_budget(ligne) for ligne in overruns(view)],
    )


def _budget_overruns_now(session: Session, association_id: str) -> list[AlerteBudget]:
    """Overrun alerts for the current open exercice's budget (current state)."""
    exercice = find_open_exercice(session, association_id, date.today())
    if exercice is None:
        return []
    view = _budget_view_for(session, association_id, exercice.id)
    if view is None:
        return []
    return [_to_alerte_budget(ligne) for ligne in overruns(view)]


def alertes(session: Session, association_id: str) -> SyntheseAlertes:
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
        budgets_depasses=_budget_overruns_now(session, association_id),
    )
