"""Budget (prévu/réalisé by category) export data gathering."""

from dataclasses import dataclass
from decimal import Decimal

from sqlmodel import Session, select

from budget_engine import build_budget_view, load_prevu, realise_par_categorie
from models import CategorieSaisie, Exercice, SensCategorie


@dataclass
class BudgetLigneExport:
    libelle: str
    prevu: Decimal
    realise: Decimal
    ecart: Decimal


@dataclass
class BudgetData:
    exercice_libelle: str
    recettes: list[BudgetLigneExport]
    depenses: list[BudgetLigneExport]
    total_recettes_prevu: Decimal
    total_recettes_realise: Decimal
    total_depenses_prevu: Decimal
    total_depenses_realise: Decimal
    resultat_prevu: Decimal
    resultat_realise: Decimal


def budget_data(
    session: Session, association_id: str, exercice: Exercice
) -> BudgetData:
    """Budget of one exercice, split into recettes and dépenses with totals."""
    categories = session.exec(
        select(CategorieSaisie).where(
            CategorieSaisie.association_id == association_id,
            CategorieSaisie.is_active.is_(True),
        )
    ).all()
    view = build_budget_view(
        categories,
        load_prevu(session, association_id, exercice.id),
        realise_par_categorie(session, association_id, exercice.id),
    )

    recettes: list[BudgetLigneExport] = []
    depenses: list[BudgetLigneExport] = []
    for ligne in view.lignes:
        target = recettes if ligne.sens == SensCategorie.RECETTE else depenses
        target.append(
            BudgetLigneExport(
                libelle=ligne.libelle,
                prevu=ligne.montant_prevu,
                realise=ligne.realise,
                ecart=ligne.ecart,
            )
        )

    return BudgetData(
        exercice_libelle=exercice.libelle,
        recettes=recettes,
        depenses=depenses,
        total_recettes_prevu=view.total_recettes_prevu,
        total_recettes_realise=view.total_recettes_realise,
        total_depenses_prevu=view.total_depenses_prevu,
        total_depenses_realise=view.total_depenses_realise,
        resultat_prevu=view.resultat_prevu,
        resultat_realise=view.resultat_realise,
    )
