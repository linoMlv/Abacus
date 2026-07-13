"""Request bodies for guided chart-of-accounts management (C10/C25)."""

from sqlmodel import SQLModel

from models import CompteType


class CreateCompteRequest(SQLModel):
    """Create an account, either guided or expert.

    Guided (the volunteer path): give ``prefixe`` — the rubrique the account
    belongs under (e.g. "606") — and the number is proposed as the first free
    child (6061, 6062…). Expert: give ``numero`` outright. The classe is always
    derived from the number, never trusted from the client.
    """

    libelle: str
    type: CompteType
    numero: str | None = None
    prefixe: str | None = None


class UpdateCompteRequest(SQLModel):
    """Rename and/or archive. The number is immutable once created: entries, the
    balance and the FEC reference it, so renumbering would rewrite history."""

    libelle: str | None = None
    is_active: bool | None = None
