"""Read access to the accounting referential (tenant-scoped).

Any active member of the association may consult its chart of accounts,
journals and fiscal years. Mutations (manual entries, closing, etc.) live in
their own permission-gated routes added in later phases.
"""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlmodel import Session, asc, desc, select

from auth_context import AccessContext, get_active_membership
from database import get_session
from models import (
    BalanceCompteRead,
    CategorieSaisie,
    CategorieSaisieRead,
    Compte,
    CompteRead,
    Ecriture,
    Exercice,
    ExerciceRead,
    GrandLivreLigneRead,
    Journal,
    JournalRead,
    LigneEcriture,
    SensCategorie,
)

ZERO = Decimal("0.00")

router = APIRouter(prefix="/api/asso/{association_id}", tags=["accounting"])


@router.get("/comptes", response_model=list[CompteRead])
def list_comptes(
    classe: int | None = Query(None, ge=1, le=8),
    include_inactive: bool = False,
    search: str | None = None,
    ctx: AccessContext = Depends(get_active_membership),
    session: Session = Depends(get_session),
):
    statement = select(Compte).where(Compte.association_id == ctx.association_id)
    if classe is not None:
        statement = statement.where(Compte.classe == classe)
    if not include_inactive:
        statement = statement.where(Compte.is_active.is_(True))
    if search:
        like = f"%{search}%"
        statement = statement.where(
            Compte.numero.contains(search) | Compte.libelle.ilike(like)
        )
    statement = statement.order_by(asc(Compte.numero))
    return session.exec(statement).all()


@router.get("/journaux", response_model=list[JournalRead])
def list_journaux(
    ctx: AccessContext = Depends(get_active_membership),
    session: Session = Depends(get_session),
):
    statement = (
        select(Journal)
        .where(Journal.association_id == ctx.association_id)
        .order_by(asc(Journal.code))
    )
    return session.exec(statement).all()


@router.get("/exercices", response_model=list[ExerciceRead])
def list_exercices(
    ctx: AccessContext = Depends(get_active_membership),
    session: Session = Depends(get_session),
):
    statement = (
        select(Exercice)
        .where(Exercice.association_id == ctx.association_id)
        .order_by(desc(Exercice.date_debut))
    )
    return session.exec(statement).all()


@router.get("/categories", response_model=list[CategorieSaisieRead])
def list_categories(
    sens: SensCategorie | None = None,
    include_inactive: bool = False,
    ctx: AccessContext = Depends(get_active_membership),
    session: Session = Depends(get_session),
):
    statement = select(CategorieSaisie).where(
        CategorieSaisie.association_id == ctx.association_id
    )
    if sens is not None:
        statement = statement.where(CategorieSaisie.sens == sens)
    if not include_inactive:
        statement = statement.where(CategorieSaisie.is_active.is_(True))
    statement = statement.order_by(asc(CategorieSaisie.ordre))
    return session.exec(statement).all()


@router.get("/balance", response_model=list[BalanceCompteRead])
def balance_comptes(
    exercice_id: str | None = None,
    ctx: AccessContext = Depends(get_active_membership),
    session: Session = Depends(get_session),
):
    """Trial balance: per account, total debit/credit and resulting solde.

    Only accounts that carry movements appear. Scope is the active association
    (double-filtered on both Compte and Ecriture); ``exercice_id`` narrows to a
    fiscal year.
    """
    debit_sum = func.coalesce(func.sum(LigneEcriture.debit), 0)
    credit_sum = func.coalesce(func.sum(LigneEcriture.credit), 0)
    statement = (
        select(Compte.id, Compte.numero, Compte.libelle, debit_sum, credit_sum)
        .join(LigneEcriture, LigneEcriture.compte_id == Compte.id)
        .join(Ecriture, Ecriture.id == LigneEcriture.ecriture_id)
        .where(
            Compte.association_id == ctx.association_id,
            Ecriture.association_id == ctx.association_id,
        )
    )
    if exercice_id is not None:
        statement = statement.where(Ecriture.exercice_id == exercice_id)
    statement = statement.group_by(Compte.id, Compte.numero, Compte.libelle).order_by(
        asc(Compte.numero)
    )

    result: list[BalanceCompteRead] = []
    for compte_id, numero, libelle, total_debit, total_credit in session.exec(
        statement
    ).all():
        td = Decimal(str(total_debit))
        tc = Decimal(str(total_credit))
        result.append(
            BalanceCompteRead(
                compte_id=compte_id,
                numero=numero,
                libelle=libelle,
                total_debit=td,
                total_credit=tc,
                solde=td - tc,
            )
        )
    return result


@router.get(
    "/comptes/{compte_id}/grand-livre", response_model=list[GrandLivreLigneRead]
)
def grand_livre(
    compte_id: str,
    exercice_id: str | None = None,
    ctx: AccessContext = Depends(get_active_membership),
    session: Session = Depends(get_session),
):
    """Ledger of one account: its movements in date order, with running balance."""
    compte = session.exec(
        select(Compte).where(
            Compte.id == compte_id, Compte.association_id == ctx.association_id
        )
    ).first()
    if compte is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Compte introuvable"
        )

    statement = (
        select(LigneEcriture, Ecriture)
        .join(Ecriture, Ecriture.id == LigneEcriture.ecriture_id)
        .where(
            LigneEcriture.compte_id == compte_id,
            Ecriture.association_id == ctx.association_id,
        )
    )
    if exercice_id is not None:
        statement = statement.where(Ecriture.exercice_id == exercice_id)
    statement = statement.order_by(
        asc(Ecriture.date), asc(Ecriture.numero_piece), asc(LigneEcriture.id)
    )

    solde = ZERO
    result: list[GrandLivreLigneRead] = []
    for ligne, ecriture in session.exec(statement).all():
        solde += ligne.debit - ligne.credit
        result.append(
            GrandLivreLigneRead(
                ecriture_id=ecriture.id,
                date=ecriture.date,
                numero_piece=ecriture.numero_piece,
                journal_id=ecriture.journal_id,
                libelle=ligne.libelle,
                debit=ligne.debit,
                credit=ligne.credit,
                solde=solde,
            )
        )
    return result
