"""Per-event financial summary (bilan d'événement) data gathering."""

from collections import OrderedDict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import func
from sqlmodel import Session, asc, select

from accounting_engine import ZERO, validated_only
from models import Compte, Ecriture, Evenement, LigneEcriture

from .common import _CHARGE, _PRODUIT, _dec


@dataclass
class EvenementOperation:
    date: date
    numero_piece: int
    libelle: str
    recette: Decimal
    depense: Decimal


@dataclass
class EvenementBilanData:
    nom: str
    description: str | None
    date_debut: date | None
    date_fin: date | None
    statut: str
    budget_recettes: Decimal | None
    budget_depenses: Decimal | None
    realise_recettes: Decimal
    realise_depenses: Decimal
    resultat: Decimal
    operations: list[EvenementOperation]


def evenement_bilan_data(
    session: Session, association_id: str, evenement: Evenement
) -> EvenementBilanData:
    """Financial summary of one event: réalisé per operation + budget."""
    rows = session.exec(
        select(
            Ecriture.id,
            Ecriture.date,
            Ecriture.numero_piece,
            Ecriture.libelle,
            Compte.classe,
            func.coalesce(func.sum(LigneEcriture.debit), 0),
            func.coalesce(func.sum(LigneEcriture.credit), 0),
        )
        .select_from(Ecriture)
        .join(LigneEcriture, LigneEcriture.ecriture_id == Ecriture.id)
        .join(Compte, Compte.id == LigneEcriture.compte_id)
        .where(
            Ecriture.association_id == association_id,
            Ecriture.evenement_id == evenement.id,
            Compte.classe.in_([_CHARGE, _PRODUIT]),
            validated_only(),
        )
        .group_by(
            Ecriture.id,
            Ecriture.date,
            Ecriture.numero_piece,
            Ecriture.libelle,
            Compte.classe,
        )
        .order_by(asc(Ecriture.date), asc(Ecriture.numero_piece))
    ).all()

    by_entry: "OrderedDict[str, EvenementOperation]" = OrderedDict()
    realise_recettes, realise_depenses = ZERO, ZERO
    for eid, jour, numero, libelle, classe, debit, credit in rows:
        op = by_entry.get(eid)
        if op is None:
            op = EvenementOperation(jour, numero, libelle, ZERO, ZERO)
            by_entry[eid] = op
        debit, credit = _dec(debit), _dec(credit)
        if classe == _PRODUIT:
            op.recette += credit - debit
            realise_recettes += credit - debit
        else:
            op.depense += debit - credit
            realise_depenses += debit - credit

    return EvenementBilanData(
        nom=evenement.nom,
        description=evenement.description,
        date_debut=evenement.date_debut,
        date_fin=evenement.date_fin,
        statut=evenement.statut.value,
        budget_recettes=evenement.budget_recettes,
        budget_depenses=evenement.budget_depenses,
        realise_recettes=realise_recettes,
        realise_depenses=realise_depenses,
        resultat=realise_recettes - realise_depenses,
        operations=list(by_entry.values()),
    )
