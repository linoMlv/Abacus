"""Income statement (compte de résultat) data gathering."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import func
from sqlmodel import Session, asc, select

from accounting_engine import ZERO, exclude_cloture, validated_only
from models import Compte, Ecriture, LigneEcriture

from .common import _CHARGE, _PRODUIT, LigneCompte, _dec


@dataclass
class CompteResultatData:
    date_from: date
    date_to: date
    charges: list[LigneCompte]
    produits: list[LigneCompte]
    total_charges: Decimal
    total_produits: Decimal
    resultat: Decimal


def compte_resultat_data(
    session: Session, association_id: str, date_from: date, date_to: date
) -> CompteResultatData:
    """Income statement over the period: each class-6/7 account with movement."""
    rows = session.exec(
        select(
            Compte.id,
            Compte.numero,
            Compte.libelle,
            Compte.classe,
            func.coalesce(func.sum(LigneEcriture.debit), 0),
            func.coalesce(func.sum(LigneEcriture.credit), 0),
        )
        .select_from(LigneEcriture)
        .join(Ecriture, Ecriture.id == LigneEcriture.ecriture_id)
        .join(Compte, Compte.id == LigneEcriture.compte_id)
        .where(
            Ecriture.association_id == association_id,
            Compte.association_id == association_id,
            Ecriture.date >= date_from,
            Ecriture.date <= date_to,
            Compte.classe.in_([_CHARGE, _PRODUIT]),
            validated_only(),
            exclude_cloture(),
        )
        .group_by(Compte.id, Compte.numero, Compte.libelle, Compte.classe)
        .order_by(asc(Compte.numero))
    ).all()

    charges: list[LigneCompte] = []
    produits: list[LigneCompte] = []
    total_charges, total_produits = ZERO, ZERO
    for _id, numero, libelle, classe, debit, credit in rows:
        debit, credit = _dec(debit), _dec(credit)
        if classe == _CHARGE:
            montant = debit - credit
            charges.append(LigneCompte(numero, libelle, montant))
            total_charges += montant
        else:
            montant = credit - debit
            produits.append(LigneCompte(numero, libelle, montant))
            total_produits += montant

    return CompteResultatData(
        date_from=date_from,
        date_to=date_to,
        charges=charges,
        produits=produits,
        total_charges=total_charges,
        total_produits=total_produits,
        resultat=total_produits - total_charges,
    )
