"""Chart of accounts: read (plan, balance, grand livre) and guided edition.

Reads are open to any member for the referential itself (it feeds form pickers)
and gated by ``REPORT_VIEW`` for the accounting restitutions (balance, grand
livre). Edition is gated by ``ACCOUNT_MANAGE`` — structural, expert territory.
"""

from decimal import Decimal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func
from sqlmodel import Session, asc, select

from accounting_engine import ZERO, validated_only
from accounting_filters import escape_like
from audit import AuditAction, record_audit
from auth_context import (
    AccessContext,
    get_active_membership,
    owned_or_404,
    require_permission,
)
from authz import Permission
from database import get_session
from http_errors import bad_request
from models import (
    BalanceCompteRead,
    Compte,
    CompteRead,
    Ecriture,
    GrandLivreLigneRead,
    LigneEcriture,
)

from .schemas import CreateCompteRequest, UpdateCompteRequest
from .service import (
    guard_archivable,
    guard_not_treasury,
    guard_treasury_numero,
    next_numero,
    numero_taken,
    validate_numero,
    validate_type,
)

router = APIRouter(prefix="/api/asso/{association_id}", tags=["comptes"])


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
        like = f"%{escape_like(search)}%"
        statement = statement.where(
            Compte.numero.contains(search, autoescape=True)
            | Compte.libelle.ilike(like, escape="\\")
        )
    statement = statement.order_by(asc(Compte.numero))
    return session.exec(statement).all()


@router.post("/comptes", response_model=CompteRead, status_code=status.HTTP_201_CREATED)
def create_compte(
    body: CreateCompteRequest,
    ctx: AccessContext = Depends(require_permission(Permission.ACCOUNT_MANAGE)),
    session: Session = Depends(get_session),
):
    """Create an account, guided (``prefixe`` → next free child) or expert
    (``numero``). The classe is derived from the number, never trusted."""
    libelle = body.libelle.strip()
    if not libelle:
        raise bad_request("Le libellé du compte est requis.")

    if body.numero is not None:
        numero = body.numero.strip()
        validate_numero(numero)
    elif body.prefixe is not None:
        numero = next_numero(session, ctx.association_id, body.prefixe.strip())
    else:
        raise bad_request("Indiquez un numéro de compte ou la rubrique parente.")

    guard_treasury_numero(numero)
    if numero_taken(session, ctx.association_id, numero):
        raise bad_request(f"Le compte {numero} existe déjà.")

    classe = validate_numero(numero)
    validate_type(classe, body.type)

    compte = Compte(
        association_id=ctx.association_id,
        numero=numero,
        libelle=libelle,
        classe=classe,
        type=body.type,
    )
    session.add(compte)
    record_audit(
        session,
        association_id=ctx.association_id,
        actor_user_id=ctx.user.id,
        action=AuditAction.COMPTE_CREATE,
        target_type="compte",
        target_id=compte.id,
        detail=f"{numero} {libelle}",
    )
    session.commit()
    session.refresh(compte)
    return compte


@router.patch("/comptes/{compte_id}", response_model=CompteRead)
def update_compte(
    compte_id: str,
    body: UpdateCompteRequest,
    ctx: AccessContext = Depends(require_permission(Permission.ACCOUNT_MANAGE)),
    session: Session = Depends(get_session),
):
    """Rename and/or archive. The number stays immutable (history references it)
    and archiving never deletes — it only hides the account from the pickers."""
    compte = owned_or_404(
        session, Compte, compte_id, ctx.association_id, "Compte introuvable"
    )
    guard_not_treasury(compte)

    if body.libelle is not None:
        libelle = body.libelle.strip()
        if not libelle:
            raise bad_request("Le libellé ne peut pas être vide.")
        compte.libelle = libelle
    if body.is_active is not None:
        if not body.is_active:
            guard_archivable(session, ctx.association_id, compte)
        compte.is_active = body.is_active

    session.add(compte)
    record_audit(
        session,
        association_id=ctx.association_id,
        actor_user_id=ctx.user.id,
        action=AuditAction.COMPTE_UPDATE,
        target_type="compte",
        target_id=compte.id,
        detail=f"{compte.numero} {compte.libelle}",
    )
    session.commit()
    session.refresh(compte)
    return compte


@router.get("/balance", response_model=list[BalanceCompteRead])
def balance_comptes(
    exercice_id: str | None = None,
    ctx: AccessContext = Depends(require_permission(Permission.REPORT_VIEW)),
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
            validated_only(),
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
    ctx: AccessContext = Depends(require_permission(Permission.REPORT_VIEW)),
    session: Session = Depends(get_session),
):
    """Ledger of one account: its movements in date order, with running balance."""
    owned_or_404(session, Compte, compte_id, ctx.association_id, "Compte introuvable")

    statement = (
        select(LigneEcriture, Ecriture)
        .join(Ecriture, Ecriture.id == LigneEcriture.ecriture_id)
        .where(
            LigneEcriture.compte_id == compte_id,
            Ecriture.association_id == ctx.association_id,
            validated_only(),
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
