"""Tenant-scoped data gathering for the exports (queries only, no rendering)."""

from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import selectinload
from sqlmodel import Session, asc, select

from accounting_engine import find_open_exercice
from models import Compte, Ecriture, Journal, LigneEcriture

ZERO = Decimal("0.00")


def _dec(value) -> Decimal:
    return Decimal(str(value)) if value is not None else ZERO


@dataclass
class Mouvement:
    date: date
    numero_piece: int
    journal_code: str
    libelle: str
    debit: Decimal
    credit: Decimal
    solde: Decimal | None = None  # running balance (relevé / grand livre)


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


def resolve_period(
    session: Session,
    association_id: str,
    date_from: date | None,
    date_to: date | None,
) -> tuple[date, date]:
    """Fill missing bounds from the open exercice (else the calendar year)."""
    if date_from and date_to:
        return date_from, date_to
    today = date.today()
    exercice = find_open_exercice(session, association_id, today)
    if exercice is not None:
        return date_from or exercice.date_debut, date_to or exercice.date_fin
    return date_from or date(today.year, 1, 1), date_to or date(today.year, 12, 31)


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


def journal_data(
    session: Session, association_id: str, date_from: date, date_to: date
) -> JournalData:
    ecritures = session.exec(
        select(Ecriture)
        .where(
            Ecriture.association_id == association_id,
            Ecriture.date >= date_from,
            Ecriture.date <= date_to,
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

    return JournalData(date_from, date_to, lignes, total_debit, total_credit)


def grand_livre_data(
    session: Session, association_id: str, date_from: date, date_to: date
) -> GrandLivreData:
    opening_rows = session.exec(
        select(
            LigneEcriture.compte_id,
            func.coalesce(func.sum(LigneEcriture.debit), 0),
            func.coalesce(func.sum(LigneEcriture.credit), 0),
        )
        .select_from(LigneEcriture)
        .join(Ecriture, Ecriture.id == LigneEcriture.ecriture_id)
        .where(Ecriture.association_id == association_id, Ecriture.date < date_from)
        .group_by(LigneEcriture.compte_id)
    ).all()
    openings = {cid: _dec(d) - _dec(c) for cid, d, c in opening_rows}

    rows = session.exec(
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
        )
        .order_by(
            asc(Compte.numero),
            asc(Ecriture.date),
            asc(Ecriture.numero_piece),
            asc(LigneEcriture.id),
        )
    ).all()

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
