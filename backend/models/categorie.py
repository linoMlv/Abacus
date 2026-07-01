import uuid
from enum import Enum

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class SensCategorie(str, Enum):
    """Direction of an assisted entry. Stable strings (persisted, audited)."""

    RECETTE = "recette"
    DEPENSE = "depense"


class CategorieSaisie(SQLModel, table=True):
    __tablename__ = "categorie_saisie"
    __table_args__ = (
        UniqueConstraint(
            "association_id", "libelle", name="uq_categorie_assoc_libelle"
        ),
    )

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    association_id: str = Field(foreign_key="association.id", index=True)
    sens: SensCategorie
    libelle: str  # parlant : "Cotisations", "Achats de fournitures", "Dons"
    compte_id: str = Field(foreign_key="compte.id")  # produit (recette) / charge
    journal_id: str = Field(foreign_key="journal.id")  # journal par défaut
    is_active: bool = Field(default=True)
    ordre: int = Field(default=0)  # ordre d'affichage dans l'écran de saisie


class CategorieSaisieRead(SQLModel):
    id: str
    sens: SensCategorie
    libelle: str
    compte_id: str
    journal_id: str
    is_active: bool
    ordre: int
