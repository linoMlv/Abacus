"""Account statement (relevé) data gathering."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import func
from sqlmodel import Session, asc, select

from accounting_engine import ZERO, validated_only
from models import Compte, Ecriture, Journal, LigneEcriture

from .common import Mouvement, _dec


@dataclass
class ReleveData:
    compte_numero: str
    compte_libelle: str
    date_from: date
    date_to: date
    solde_initial: Decimal
    solde_final: Decimal
    total_debit: Decimal
    total_credit: Decimal
    mouvements: list[Mouvement]


def releve_data(
    session: Session,
    association_id: str,
    compte: Compte,
    date_from: date,
    date_to: date,
) -> ReleveData:
    opening_debit, opening_credit = session.exec(
        select(
            func.coalesce(func.sum(LigneEcriture.debit), 0),
            func.coalesce(func.sum(LigneEcriture.credit), 0),
        )
        .select_from(LigneEcriture)
        .join(Ecriture, Ecriture.id == LigneEcriture.ecriture_id)
        .where(
            Ecriture.association_id == association_id,
            LigneEcriture.compte_id == compte.id,
            Ecriture.date < date_from,
            validated_only(),
        )
    ).one()
    solde = _dec(opening_debit) - _dec(opening_credit)
    opening = solde

    rows = session.exec(
        select(
            Ecriture.date,
            Ecriture.numero_piece,
            Journal.code,
            LigneEcriture.libelle,
            LigneEcriture.debit,
            LigneEcriture.credit,
        )
        .select_from(LigneEcriture)
        .join(Ecriture, Ecriture.id == LigneEcriture.ecriture_id)
        .join(Journal, Journal.id == Ecriture.journal_id)
        .where(
            Ecriture.association_id == association_id,
            LigneEcriture.compte_id == compte.id,
            Ecriture.date >= date_from,
            Ecriture.date <= date_to,
            validated_only(),
        )
        .order_by(asc(Ecriture.date), asc(Ecriture.numero_piece), asc(LigneEcriture.id))
    ).all()

    total_debit, total_credit = ZERO, ZERO
    mouvements: list[Mouvement] = []
    for jour, numero, code, libelle, debit, credit in rows:
        debit, credit = _dec(debit), _dec(credit)
        total_debit += debit
        total_credit += credit
        solde += debit - credit
        mouvements.append(Mouvement(jour, numero, code, libelle, debit, credit, solde))

    return ReleveData(
        compte_numero=compte.numero,
        compte_libelle=compte.libelle,
        date_from=date_from,
        date_to=date_to,
        solde_initial=opening,
        solde_final=solde,
        total_debit=total_debit,
        total_credit=total_credit,
        mouvements=mouvements,
    )
