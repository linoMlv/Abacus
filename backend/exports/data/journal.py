"""Journal and grand livre (general ledger) data gathering."""

from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import selectinload
from sqlmodel import Session, asc, select

from accounting_engine import ZERO, scope_exercice, validated_only
from accounting_filters import JournalFilter, journal_filter_clauses
from models import Compte, Ecriture, Journal, LigneEcriture

from .common import Mouvement, _dec


@dataclass
class JournalLigne:
    date: date
    numero_piece: int
    journal_code: str
    compte: str
    libelle: str
    debit: Decimal
    credit: Decimal
    first_of_entry: bool


@dataclass
class JournalData:
    date_from: date
    date_to: date
    lignes: list[JournalLigne]
    total_debit: Decimal
    total_credit: Decimal


@dataclass
class CompteLedger:
    numero: str
    libelle: str
    solde_initial: Decimal
    total_debit: Decimal = ZERO
    total_credit: Decimal = ZERO
    solde_final: Decimal = ZERO
    mouvements: list[Mouvement] = field(default_factory=list)


@dataclass
class GrandLivreData:
    date_from: date
    date_to: date
    comptes: list[CompteLedger]


def journal_data(
    session: Session, association_id: str, filtre: JournalFilter
) -> JournalData:
    """Journal export over ``filtre``'s period, honoring its faceted filters.

    Uses the same ``journal_filter_clauses`` as the journal listing, so the
    exported document matches exactly what the user filtered on screen.
    """
    ecritures = session.exec(
        select(Ecriture)
        .where(
            Ecriture.association_id == association_id,
            *journal_filter_clauses(association_id, filtre),
        )
        .order_by(asc(Ecriture.date), asc(Ecriture.numero_piece))
        .options(selectinload(Ecriture.lignes))
    ).all()
    comptes = {
        c.id: c
        for c in session.exec(
            select(Compte).where(Compte.association_id == association_id)
        ).all()
    }
    journaux = {
        j.id: j.code
        for j in session.exec(
            select(Journal).where(Journal.association_id == association_id)
        ).all()
    }

    lignes: list[JournalLigne] = []
    total_debit, total_credit = ZERO, ZERO
    for ecriture in ecritures:
        code = journaux.get(ecriture.journal_id, "")
        # Debit lines first (accounting convention), then a stable id order.
        ordered = sorted(ecriture.lignes, key=lambda x: (x.credit != 0, x.id))
        for index, ligne in enumerate(ordered):
            compte = comptes.get(ligne.compte_id)
            label = f"{compte.numero} {compte.libelle}" if compte else ""
            debit, credit = _dec(ligne.debit), _dec(ligne.credit)
            total_debit += debit
            total_credit += credit
            lignes.append(
                JournalLigne(
                    date=ecriture.date,
                    numero_piece=ecriture.numero_piece,
                    journal_code=code,
                    compte=label,
                    libelle=ligne.libelle,
                    debit=debit,
                    credit=credit,
                    first_of_entry=index == 0,
                )
            )

    return JournalData(
        filtre.date_from, filtre.date_to, lignes, total_debit, total_credit
    )


def grand_livre_data(
    session: Session, association_id: str, date_from: date, date_to: date
) -> GrandLivreData:
    # Scope to the exercice of the period start so a report à nouveau (which
    # restates class 1-5 openings at the year's start) is not double-counted with
    # prior years' movements. The opening then stays within the exercice: a
    # report à nouveau dated on date_debut lands in the movements, not the opening.
    exercice = scope_exercice(session, association_id, date_from)
    exercice_id = exercice.id if exercice is not None else None

    opening_stmt = (
        select(
            LigneEcriture.compte_id,
            func.coalesce(func.sum(LigneEcriture.debit), 0),
            func.coalesce(func.sum(LigneEcriture.credit), 0),
        )
        .select_from(LigneEcriture)
        .join(Ecriture, Ecriture.id == LigneEcriture.ecriture_id)
        .where(
            Ecriture.association_id == association_id,
            Ecriture.date < date_from,
            validated_only(),
        )
        .group_by(LigneEcriture.compte_id)
    )
    if exercice_id is not None:
        opening_stmt = opening_stmt.where(Ecriture.exercice_id == exercice_id)
    openings = {
        cid: _dec(d) - _dec(c) for cid, d, c in session.exec(opening_stmt).all()
    }

    movements_stmt = (
        select(
            LigneEcriture.compte_id,
            Compte.numero,
            Compte.libelle,
            Ecriture.date,
            Ecriture.numero_piece,
            Journal.code,
            LigneEcriture.libelle,
            LigneEcriture.debit,
            LigneEcriture.credit,
        )
        .select_from(LigneEcriture)
        .join(Ecriture, Ecriture.id == LigneEcriture.ecriture_id)
        .join(Compte, Compte.id == LigneEcriture.compte_id)
        .join(Journal, Journal.id == Ecriture.journal_id)
        .where(
            Ecriture.association_id == association_id,
            Ecriture.date >= date_from,
            Ecriture.date <= date_to,
            validated_only(),
        )
        .order_by(
            asc(Compte.numero),
            asc(Ecriture.date),
            asc(Ecriture.numero_piece),
            asc(LigneEcriture.id),
        )
    )
    if exercice_id is not None:
        movements_stmt = movements_stmt.where(Ecriture.exercice_id == exercice_id)
    rows = session.exec(movements_stmt).all()

    ledgers: "OrderedDict[str, CompteLedger]" = OrderedDict()
    for (
        cid,
        numero,
        libelle,
        jour,
        numero_piece,
        code,
        libelle_l,
        debit,
        credit,
    ) in rows:
        ledger = ledgers.get(cid)
        if ledger is None:
            opening = openings.get(cid, ZERO)
            ledger = CompteLedger(
                numero=numero,
                libelle=libelle,
                solde_initial=opening,
                solde_final=opening,
            )
            ledgers[cid] = ledger
        debit, credit = _dec(debit), _dec(credit)
        ledger.total_debit += debit
        ledger.total_credit += credit
        ledger.solde_final += debit - credit
        ledger.mouvements.append(
            Mouvement(
                jour, numero_piece, code, libelle_l, debit, credit, ledger.solde_final
            )
        )

    return GrandLivreData(date_from, date_to, list(ledgers.values()))
