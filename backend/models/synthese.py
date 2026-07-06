from datetime import date
from decimal import Decimal

from sqlmodel import SQLModel

from .categorie import SensCategorie


class SyntheseResultat(SQLModel):
    """Result over the period: produits (cl.7) − charges (cl.6)."""

    recettes: Decimal
    depenses: Decimal
    resultat: Decimal


class RepartitionCategorieItem(SQLModel):
    """One slice of the per-category breakdown over the period."""

    categorie_id: str
    libelle: str
    sens: SensCategorie
    montant: Decimal


class RepartitionEvenementItem(SQLModel):
    """One slice of the per-event breakdown over the period."""

    evenement_id: str
    nom: str
    couleur: str | None
    recettes: Decimal
    depenses: Decimal
    resultat: Decimal


class CourbePoint(SQLModel):
    """One point of the treasury balance curve (cumulative end-of-day balance)."""

    date: date
    solde: Decimal


class AlerteEvenement(SQLModel):
    evenement_id: str
    nom: str
    budget_depenses: Decimal
    realise_depenses: Decimal


class AlerteExercice(SQLModel):
    exercice_id: str
    libelle: str
    date_fin: date


class AlerteBudget(SQLModel):
    """A budgeted dépense category whose réalisé exceeds its prévu amount."""

    categorie_id: str
    libelle: str
    montant_prevu: Decimal
    realise: Decimal


class SyntheseAlertes(SQLModel):
    """Current actionable alerts (independent of the selected period)."""

    brouillons: int  # entries still in draft, to validate
    evenements_depasses: list[AlerteEvenement]
    exercices_a_cloturer: list[AlerteExercice]
    budgets_depasses: list[AlerteBudget]


class BudgetSynthese(SQLModel):
    """Dashboard budget widget: prévu vs réalisé of the period's exercice budget."""

    exercice_id: str
    exercice_libelle: str
    recettes_prevu: Decimal
    recettes_realise: Decimal
    depenses_prevu: Decimal
    depenses_realise: Decimal
    resultat_prevu: Decimal
    resultat_realise: Decimal
    depassements: list[AlerteBudget]


class SyntheseRead(SQLModel):
    """Consolidated dashboard: period analytics + current alerts, in one read."""

    date_from: date
    date_to: date
    resultat: SyntheseResultat
    repartition_categories: list[RepartitionCategorieItem]
    repartition_evenements: list[RepartitionEvenementItem]
    courbe_tresorerie: list[CourbePoint]
    alertes: SyntheseAlertes
    budget: "BudgetSynthese | None" = None
