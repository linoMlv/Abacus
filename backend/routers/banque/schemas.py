"""Request/response bodies for the bank reconciliation endpoints."""

from sqlmodel import SQLModel

from models import ModeReglement


class RapprocherRequest(SQLModel):
    """Lettrer a statement line to an existing accounting entry."""

    ecriture_id: str


class CreerEcritureRequest(SQLModel):
    """Create an assisted entry from a statement line, then lettrer it.

    The sens (recette/dépense) is derived from the line's sign; the chosen
    category must match it. The treasury account and amount/date/libellé come
    from the statement line — only the analytic metadata is provided here.
    """

    categorie_id: str
    evenement_id: str | None = None
    tiers_id: str | None = None
    reference_externe: str | None = None
    mode_reglement: ModeReglement | None = None
