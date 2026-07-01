"""Balance sheet (bilan ANC) data gathering."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import func
from sqlmodel import Session, asc, select

from accounting_engine import ZERO, exclude_cloture, scope_exercice, validated_only
from models import Compte, Ecriture, ExerciceStatut, LigneEcriture

from .common import _BALANCE_CLASSES, _CHARGE, _PRODUIT, LigneCompte, _dec


@dataclass
class BilanData:
    date_to: date
    actif: list[LigneCompte]
    passif: list[LigneCompte]
    resultat: Decimal
    total_actif: Decimal
    total_passif: Decimal


def bilan_data(session: Session, association_id: str, date_to: date) -> BilanData:
    """Balance sheet at ``date_to``: class 1-5 balances of the covering exercice.

    Each class 1-5 account is placed on the side of its balance (debit → actif,
    credit → passif). Figures are scoped to the exercice covering ``date_to`` so a
    report à nouveau (which restates the opening balances) is never double-counted
    across the closing boundary. If that exercice is still open, the running
    result (produits − charges, excluding the determination) is added to the
    passif so actif = passif; once closed, the result already sits in the 12
    account among the class-1-5 balances, so it is not added again.
    """
    exercice = scope_exercice(session, association_id, date_to)
    exercice_id = exercice.id if exercice is not None else None
    is_cloture = exercice is not None and exercice.statut == ExerciceStatut.CLOTURE

    balance_stmt = (
        select(
            Compte.id,
            Compte.numero,
            Compte.libelle,
            func.coalesce(func.sum(LigneEcriture.debit), 0),
            func.coalesce(func.sum(LigneEcriture.credit), 0),
        )
        .select_from(LigneEcriture)
        .join(Ecriture, Ecriture.id == LigneEcriture.ecriture_id)
        .join(Compte, Compte.id == LigneEcriture.compte_id)
        .where(
            Ecriture.association_id == association_id,
            Compte.association_id == association_id,
            Ecriture.date <= date_to,
            Compte.classe.in_(_BALANCE_CLASSES),
            validated_only(),
        )
        .group_by(Compte.id, Compte.numero, Compte.libelle)
        .order_by(asc(Compte.numero))
    )
    if exercice_id is not None:
        balance_stmt = balance_stmt.where(Ecriture.exercice_id == exercice_id)

    actif: list[LigneCompte] = []
    passif: list[LigneCompte] = []
    total_actif, total_passif = ZERO, ZERO
    for _id, numero, libelle, debit, credit in session.exec(balance_stmt).all():
        solde = _dec(debit) - _dec(credit)
        if solde > ZERO:
            actif.append(LigneCompte(numero, libelle, solde))
            total_actif += solde
        elif solde < ZERO:
            passif.append(LigneCompte(numero, libelle, -solde))
            total_passif += -solde

    resultat = ZERO
    if not is_cloture:
        res_stmt = (
            select(
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
                Ecriture.date <= date_to,
                Compte.classe.in_([_CHARGE, _PRODUIT]),
                validated_only(),
                exclude_cloture(),
            )
            .group_by(Compte.classe)
        )
        if exercice_id is not None:
            res_stmt = res_stmt.where(Ecriture.exercice_id == exercice_id)
        produits, charges = ZERO, ZERO
        for classe, debit, credit in session.exec(res_stmt).all():
            if classe == _PRODUIT:
                produits += _dec(credit) - _dec(debit)
            else:
                charges += _dec(debit) - _dec(credit)
        resultat = produits - charges

    return BilanData(
        date_to=date_to,
        actif=actif,
        passif=passif,
        resultat=resultat,
        total_actif=total_actif,
        total_passif=total_passif + resultat,
    )
