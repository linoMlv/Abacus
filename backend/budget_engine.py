"""Budget computation (Phase 5): budget vs réalisé, by category, per exercice.

The budget is expressed in the treasurer's own **catégories parlantes** (§15.5):
one prévu amount per category for a fiscal year. The *réalisé* is derived from
the ledger — the validated class-6/7 movement of the entries tagged with each
category — so it never drifts from what was actually booked. This module holds
the pure domain logic shared by the budget router, the dashboard synthesis and
the exports; it performs no authorization (callers pass a server-resolved
``association_id``) and never mutates.
"""

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func
from sqlmodel import Session, select

from accounting_engine import (
    CENTS,
    CLASSES_GESTION,
    ZERO,
    to_decimal,
    validated_only,
)
from models import (
    Budget,
    CategorieSaisie,
    Compte,
    Ecriture,
    LigneBudget,
    LigneEcriture,
    SensCategorie,
)


@dataclass
class BudgetLigneView:
    """One budget row: a category with its prévu, réalisé and écart."""

    categorie_id: str
    libelle: str
    sens: SensCategorie
    montant_prevu: Decimal
    realise: Decimal
    ecart: Decimal


@dataclass
class BudgetView:
    """A whole exercice budget: rows plus totals and the prévisionnel result."""

    lignes: list[BudgetLigneView]
    total_recettes_prevu: Decimal
    total_recettes_realise: Decimal
    total_depenses_prevu: Decimal
    total_depenses_realise: Decimal
    resultat_prevu: Decimal
    resultat_realise: Decimal


def realise_par_categorie(
    session: Session, association_id: str, exercice_id: str
) -> dict[str, Decimal]:
    """Réalisé per category over one exercice: signed class-6/7 movement.

    Only validated entries count (an official figure, §D38); the entry's own
    produit/charge line is summed and signed by the category's sens (recette =
    crédit − débit, dépense = débit − crédit). The join on ``categorie_id``
    naturally excludes untagged and closing entries. Scoped to the exercice so a
    report à nouveau of another year can never leak in.
    """
    rows = session.exec(
        select(
            CategorieSaisie.id,
            CategorieSaisie.sens,
            func.coalesce(func.sum(LigneEcriture.debit), 0),
            func.coalesce(func.sum(LigneEcriture.credit), 0),
        )
        .select_from(Ecriture)
        .join(CategorieSaisie, CategorieSaisie.id == Ecriture.categorie_id)
        .join(LigneEcriture, LigneEcriture.ecriture_id == Ecriture.id)
        .join(Compte, Compte.id == LigneEcriture.compte_id)
        .where(
            Ecriture.association_id == association_id,
            CategorieSaisie.association_id == association_id,
            Ecriture.exercice_id == exercice_id,
            Compte.classe.in_(CLASSES_GESTION),
            validated_only(),
        )
        .group_by(CategorieSaisie.id, CategorieSaisie.sens)
    ).all()

    out: dict[str, Decimal] = {}
    for categorie_id, sens, total_debit, total_credit in rows:
        debit, credit = to_decimal(total_debit), to_decimal(total_credit)
        montant = credit - debit if sens == SensCategorie.RECETTE else debit - credit
        out[categorie_id] = montant.quantize(CENTS)
    return out


def load_prevu(
    session: Session, association_id: str, exercice_id: str
) -> dict[str, Decimal]:
    """The prévu amount per category for an exercice budget (empty if none)."""
    budget = session.exec(
        select(Budget).where(
            Budget.association_id == association_id,
            Budget.exercice_id == exercice_id,
        )
    ).first()
    if budget is None:
        return {}
    return {
        ligne.categorie_id: ligne.montant_prevu
        for ligne in session.exec(
            select(LigneBudget).where(LigneBudget.budget_id == budget.id)
        ).all()
    }


def _sort_key(categorie: CategorieSaisie) -> tuple[int, int, str]:
    """Recettes before dépenses, then by display order, then label."""
    return (
        0 if categorie.sens == SensCategorie.RECETTE else 1,
        categorie.ordre,
        categorie.libelle,
    )


def build_budget_view(
    categories: list[CategorieSaisie],
    prevu: dict[str, Decimal],
    realise: dict[str, Decimal],
) -> BudgetView:
    """Assemble the budget view from the categories, the prévu and réalisé maps.

    Every category is listed (a null budget line reads as prévu 0), so the caller
    gets a full grid to fill in. Totals are split by sens and the prévisionnel /
    réalisé results are recettes − dépenses.
    """
    lignes: list[BudgetLigneView] = []
    totals = {
        SensCategorie.RECETTE: [ZERO, ZERO],  # [prévu, réalisé]
        SensCategorie.DEPENSE: [ZERO, ZERO],
    }
    for categorie in sorted(categories, key=_sort_key):
        montant_prevu = prevu.get(categorie.id, ZERO).quantize(CENTS)
        montant_realise = realise.get(categorie.id, ZERO).quantize(CENTS)
        lignes.append(
            BudgetLigneView(
                categorie_id=categorie.id,
                libelle=categorie.libelle,
                sens=categorie.sens,
                montant_prevu=montant_prevu,
                realise=montant_realise,
                ecart=montant_realise - montant_prevu,
            )
        )
        totals[categorie.sens][0] += montant_prevu
        totals[categorie.sens][1] += montant_realise

    recettes_prevu, recettes_realise = totals[SensCategorie.RECETTE]
    depenses_prevu, depenses_realise = totals[SensCategorie.DEPENSE]
    return BudgetView(
        lignes=lignes,
        total_recettes_prevu=recettes_prevu,
        total_recettes_realise=recettes_realise,
        total_depenses_prevu=depenses_prevu,
        total_depenses_realise=depenses_realise,
        resultat_prevu=recettes_prevu - depenses_prevu,
        resultat_realise=recettes_realise - depenses_realise,
    )


def overruns(view: BudgetView) -> list[BudgetLigneView]:
    """Dépense rows that exceeded a positive budget, worst overrun first."""
    over = [
        ligne
        for ligne in view.lignes
        if ligne.sens == SensCategorie.DEPENSE
        and ligne.montant_prevu > ZERO
        and ligne.realise > ligne.montant_prevu
    ]
    over.sort(key=lambda ligne: ligne.ecart, reverse=True)
    return over
