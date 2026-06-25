"""Read access to the accounting referential (tenant-scoped).

Any active member of the association may consult its chart of accounts,
journals and fiscal years. Mutations (manual entries, closing, etc.) live in
their own permission-gated routes added in later phases.
"""

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, asc, desc, select

from auth_context import AccessContext, get_active_membership
from database import get_session
from models import (
    Compte,
    CompteRead,
    Exercice,
    ExerciceRead,
    Journal,
    JournalRead,
)

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
