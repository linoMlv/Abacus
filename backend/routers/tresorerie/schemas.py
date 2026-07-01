"""Request bodies for the treasury endpoints."""

from datetime import date
from decimal import Decimal

from sqlmodel import SQLModel

from models import TypeTresorerie


class CreateTresorerieRequest(SQLModel):
    nom: str
    type_tresorerie: TypeTresorerie
    iban: str | None = None
    couleur: str | None = None
    solde_initial: Decimal | None = None
    date_solde_initial: date | None = None


class UpdateTresorerieRequest(SQLModel):
    nom: str | None = None
    type_tresorerie: TypeTresorerie | None = None
    iban: str | None = None
    couleur: str | None = None
    ordre: int | None = None
    is_active: bool | None = None


class SetSoldeInitialRequest(SQLModel):
    montant: Decimal  # 0 removes the opening balance
    date_solde_initial: date | None = None
