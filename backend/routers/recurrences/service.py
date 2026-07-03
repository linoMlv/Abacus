"""Tenant-scoped resolution & validation for recurring-entry templates.

Every id from the client (category, treasury account, tiers, event, recurrence)
is re-resolved against the active association before use — reusing the very same
resolution helpers as manual saisie, so a recurrence can only ever reference the
association's own, active accounting objects.
"""

from decimal import Decimal

from sqlmodel import Session, select

from accounting_engine import CENTS
from auth_context import owned_or_404
from models import CategorieSaisie, Compte, Recurrence
from routers.ecritures.resolution import (
    _bad_request,
    _owned_treasury,
    _resolve_evenement_id,
    _resolve_tiers_id,
)

_ZERO = Decimal("0")


def owned_recurrence(
    session: Session, association_id: str, recurrence_id: str
) -> Recurrence:
    return owned_or_404(
        session, Recurrence, recurrence_id, association_id, "Récurrence introuvable"
    )


def resolve_categorie(
    session: Session, association_id: str, categorie_id: str
) -> CategorieSaisie:
    categorie = session.exec(
        select(CategorieSaisie).where(
            CategorieSaisie.id == categorie_id,
            CategorieSaisie.association_id == association_id,
            CategorieSaisie.is_active.is_(True),
        )
    ).first()
    if categorie is None:
        raise _bad_request("Catégorie introuvable ou inactive.")
    return categorie


def resolve_compte_tresorerie(
    session: Session, association_id: str, compte_id: str
) -> Compte:
    return _owned_treasury(session, association_id, compte_id)


def resolve_tiers_id(
    session: Session, association_id: str, tiers_id: str | None
) -> str | None:
    return _resolve_tiers_id(session, association_id, tiers_id)


def resolve_evenement_id(
    session: Session, association_id: str, evenement_id: str | None
) -> str | None:
    return _resolve_evenement_id(session, association_id, evenement_id)


def clean_montant(montant: Decimal) -> Decimal:
    montant = montant.quantize(CENTS)
    if montant <= _ZERO:
        raise _bad_request("Le montant doit être strictement positif.")
    return montant


def check_dates(prochaine_echeance, date_fin) -> None:
    if date_fin is not None and date_fin < prochaine_echeance:
        raise _bad_request(
            "La date de fin doit être postérieure à la prochaine échéance."
        )
