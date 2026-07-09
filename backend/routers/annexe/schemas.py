"""Request bodies for the narrative-annexe endpoints."""

from sqlmodel import SQLModel


class RubriqueCreate(SQLModel):
    """Add a narrative rubric to an exercice's annexe."""

    titre: str
    contenu: str = ""


class RubriqueUpdate(SQLModel):
    """Edit a rubric's title and/or body (only the provided fields change)."""

    titre: str | None = None
    contenu: str | None = None


class RubriqueReorder(SQLModel):
    """New display order: the full list of the exercice's rubric ids."""

    ids: list[str]
