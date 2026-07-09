import uuid

from sqlmodel import Field, SQLModel

# Standard ANC 2018-06 annexe rubrics, seeded (empty) for every exercice so the
# treasurer is guided rather than facing a blank page. The list is authoritative
# for the default set; a rubric is otherwise free (add / rename / reorder / delete).
DEFAULT_ANNEXE_RUBRIQUES: tuple[str, ...] = (
    "Règles et méthodes comptables",
    "Faits marquants de l'exercice",
    "Événements postérieurs à la clôture",
    "Engagements financiers et hors bilan",
    "Informations sur les fonds dédiés",
)


class AnnexeRubrique(SQLModel, table=True):
    """A narrative section of an exercice's annexe (ANC comptes annuels).

    Belongs to one exercice; carries a free-text title and body the association
    fills in. Distinct from the *computed* annexe tables (fonds dédiés, etc.),
    which are derived from the ledger — this is the human commentary.
    """

    __tablename__ = "annexe_rubrique"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    association_id: str = Field(foreign_key="association.id", index=True)
    exercice_id: str = Field(foreign_key="exercice.id", index=True)
    titre: str
    contenu: str = Field(default="")
    ordre: int = Field(default=0)  # display order within the exercice's annexe


class AnnexeRubriqueRead(SQLModel):
    id: str
    exercice_id: str
    titre: str
    contenu: str
    ordre: int
