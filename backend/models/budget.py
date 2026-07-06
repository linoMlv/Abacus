import uuid
from decimal import Decimal

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from .categorie import SensCategorie
from .referentiel import ExerciceStatut


class Budget(SQLModel, table=True):
    """A fiscal-year budget: a prévu amount per category (§15.5, Phase 5).

    One budget per (association, exercice); its ``LigneBudget`` rows hold the
    prévu amounts. The réalisé is always recomputed from the ledger (never
    stored). Lines are managed explicitly by the service (flush parent before
    children for the FK), not through an ORM relationship.
    """

    __tablename__ = "budget"
    __table_args__ = (
        UniqueConstraint(
            "association_id", "exercice_id", name="uq_budget_assoc_exercice"
        ),
    )

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    association_id: str = Field(foreign_key="association.id", index=True)
    exercice_id: str = Field(foreign_key="exercice.id", index=True)


class LigneBudget(SQLModel, table=True):
    """The prévu amount budgeted for one category within a budget."""

    __tablename__ = "ligne_budget"
    __table_args__ = (
        UniqueConstraint("budget_id", "categorie_id", name="uq_ligne_budget_cat"),
    )

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    budget_id: str = Field(foreign_key="budget.id", index=True)
    categorie_id: str = Field(foreign_key="categorie_saisie.id", index=True)
    montant_prevu: Decimal = Field(max_digits=12, decimal_places=2)


class LigneBudgetRead(SQLModel):
    """One budget row served to the client: prévu, réalisé and écart."""

    categorie_id: str
    libelle: str
    sens: SensCategorie
    montant_prevu: Decimal
    realise: Decimal
    ecart: Decimal


class BudgetRead(SQLModel):
    """The budget of one exercice: every active category, with totals and results."""

    exercice_id: str
    exercice_libelle: str
    exercice_statut: ExerciceStatut
    lignes: list[LigneBudgetRead]
    total_recettes_prevu: Decimal
    total_recettes_realise: Decimal
    total_depenses_prevu: Decimal
    total_depenses_realise: Decimal
    resultat_prevu: Decimal
    resultat_realise: Decimal


class LigneBudgetInput(SQLModel):
    categorie_id: str
    montant_prevu: Decimal


class BudgetUpsert(SQLModel):
    """Replace the prévu amounts of an exercice budget in one shot.

    Missing or zero amounts leave no line (a full grid is rebuilt from these).
    """

    exercice_id: str
    lignes: list[LigneBudgetInput]
