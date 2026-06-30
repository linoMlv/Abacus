"""Tenant-scoped data gathering for the exports (queries only, no rendering)."""

from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import selectinload
from sqlmodel import Session, asc, select

from accounting_engine import ZERO, find_open_exercice, validated_only
from accounting_filters import JournalFilter, journal_filter_clauses
from models import Compte, Ecriture, Evenement, Journal, LigneEcriture

_CHARGE, _PRODUIT = 6, 7
_BALANCE_CLASSES = (1, 2, 3, 4, 5)


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


@dataclass
class LigneCompte:
    numero: str
    libelle: str
    montant: Decimal


@dataclass
class CompteResultatData:
    date_from: date
    date_to: date
    charges: list[LigneCompte]
    produits: list[LigneCompte]
    total_charges: Decimal
    total_produits: Decimal
    resultat: Decimal


@dataclass
class BilanData:
    date_to: date
    actif: list[LigneCompte]
    passif: list[LigneCompte]
    resultat: Decimal
    total_actif: Decimal
    total_passif: Decimal


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
    opening_rows = session.exec(
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
            validated_only(),
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


def bilan_data(session: Session, association_id: str, date_to: date) -> BilanData:
    """Balance sheet at ``date_to``: cumulative class 1-5 balances + result.

    Each class 1-5 account is placed on the side of its cumulative balance
    (debit → actif, credit → passif). The result (cumulative produits − charges
    up to ``date_to``) is added to the passif so that actif = passif, since the
    books are not yet closed (the report à nouveau is a later phase).
    """
    rows = session.exec(
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
    ).all()

    actif: list[LigneCompte] = []
    passif: list[LigneCompte] = []
    total_actif, total_passif = ZERO, ZERO
    for _id, numero, libelle, debit, credit in rows:
        solde = _dec(debit) - _dec(credit)
        if solde > ZERO:
            actif.append(LigneCompte(numero, libelle, solde))
            total_actif += solde
        elif solde < ZERO:
            passif.append(LigneCompte(numero, libelle, -solde))
            total_passif += -solde

    res_rows = session.exec(
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
        )
        .group_by(Compte.classe)
    ).all()
    produits, charges = ZERO, ZERO
    for classe, debit, credit in res_rows:
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
