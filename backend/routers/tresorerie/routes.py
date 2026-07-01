"""Treasury endpoints: list, create, set opening balance, update/archive."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlmodel import Session, asc, select

from accounting_engine import CENTS, ZERO
from audit import AuditAction, record_audit
from auth_context import AccessContext, get_active_membership, require_permission
from authz import Permission
from database import get_session
from models import Compte, CompteTresorerieRead, CompteType

from .schemas import (
    CreateTresorerieRequest,
    SetSoldeInitialRequest,
    UpdateTresorerieRequest,
)
from .service import (
    _TYPE_PREFIX,
    _a_nouveau_entries,
    _bad_request,
    _next_treasury_numero,
    _owned_treasury,
    _post_solde_initial,
    _to_read,
    _treasury_soldes,
)

router = APIRouter(prefix="/api/asso/{association_id}", tags=["tresorerie"])


@router.get("/tresorerie", response_model=list[CompteTresorerieRead])
def list_tresorerie(
    include_inactive: bool = False,
    ctx: AccessContext = Depends(get_active_membership),
    session: Session = Depends(get_session),
):
    """The association's treasury accounts with their current balances."""
    statement = select(Compte).where(
        Compte.association_id == ctx.association_id,
        Compte.type_tresorerie.is_not(None),
    )
    if not include_inactive:
        statement = statement.where(Compte.is_active.is_(True))
    comptes = session.exec(
        statement.order_by(asc(Compte.ordre), asc(Compte.numero))
    ).all()

    soldes = _treasury_soldes(session, ctx.association_id, [c.id for c in comptes])
    return [_to_read(c, soldes.get(c.id, ZERO)) for c in comptes]


@router.post(
    "/tresorerie",
    response_model=CompteTresorerieRead,
    status_code=status.HTTP_201_CREATED,
)
def create_tresorerie(
    body: CreateTresorerieRequest,
    ctx: AccessContext = Depends(require_permission(Permission.TRESORERIE_MANAGE)),
    session: Session = Depends(get_session),
):
    nom = body.nom.strip()
    if not nom:
        raise _bad_request("Le nom du compte est requis.")

    numero = _next_treasury_numero(
        session, ctx.association_id, _TYPE_PREFIX[body.type_tresorerie]
    )
    max_ordre = session.exec(
        select(func.coalesce(func.max(Compte.ordre), -1)).where(
            Compte.association_id == ctx.association_id,
            Compte.type_tresorerie.is_not(None),
        )
    ).one()

    compte = Compte(
        association_id=ctx.association_id,
        numero=numero,
        libelle=nom,
        classe=int(numero[0]),
        type=CompteType.ACTIF,
        type_tresorerie=body.type_tresorerie,
        iban=(body.iban or None),
        couleur=(body.couleur or None),
        ordre=max_ordre + 1,
    )
    session.add(compte)
    # Persist the account before the à-nouveau entry references it (FK ordering).
    session.flush()

    if body.solde_initial is not None and body.solde_initial != ZERO:
        jour = body.date_solde_initial or date.today()
        _post_solde_initial(session, ctx, compte, body.solde_initial, jour)

    record_audit(
        session,
        association_id=ctx.association_id,
        actor_user_id=ctx.user.id,
        action=AuditAction.COMPTE_TRESORERIE_CREATE,
        target_type="compte",
        target_id=compte.id,
        detail=f"{numero} {nom}",
    )
    session.commit()
    session.refresh(compte)

    solde = _treasury_soldes(session, ctx.association_id, [compte.id]).get(
        compte.id, ZERO
    )
    return _to_read(compte, solde)


@router.post(
    "/tresorerie/{compte_id}/solde-initial", response_model=CompteTresorerieRead
)
def set_solde_initial(
    compte_id: str,
    body: SetSoldeInitialRequest,
    ctx: AccessContext = Depends(require_permission(Permission.TRESORERIE_MANAGE)),
    session: Session = Depends(get_session),
):
    """Set the opening balance of an existing treasury account (onboarding).

    Useful for the seeded Banque/Caisse. The opening balance posts D account /
    C report à nouveau (110) and is **validated on creation**, so it counts at
    once and is then immutable: a second attempt is refused (409 — adjusting it
    goes through a contre-passation, like any validated entry). A zero amount on
    an account with no opening balance is a no-op.
    """
    compte = _owned_treasury(session, ctx.association_id, compte_id)

    existing = _a_nouveau_entries(session, ctx.association_id, compte.id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Le solde initial est déjà défini et ne peut plus être modifié "
            "(contre-passation requise).",
        )

    montant = body.montant.quantize(CENTS)
    if montant != ZERO:
        jour = body.date_solde_initial or date.today()
        _post_solde_initial(session, ctx, compte, montant, jour)

    record_audit(
        session,
        association_id=ctx.association_id,
        actor_user_id=ctx.user.id,
        action=AuditAction.COMPTE_TRESORERIE_UPDATE,
        target_type="compte",
        target_id=compte.id,
        detail=f"solde initial {montant}",
    )
    session.commit()
    session.refresh(compte)

    solde = _treasury_soldes(session, ctx.association_id, [compte.id]).get(
        compte.id, ZERO
    )
    return _to_read(compte, solde)


@router.patch("/tresorerie/{compte_id}", response_model=CompteTresorerieRead)
def update_tresorerie(
    compte_id: str,
    body: UpdateTresorerieRequest,
    ctx: AccessContext = Depends(require_permission(Permission.TRESORERIE_MANAGE)),
    session: Session = Depends(get_session),
):
    """Rename / recolour / reorder / archive a treasury account.

    Archiving (``is_active = false``) never deletes: the ledger history stays
    valid. The account number is stable (kept for audit/FEC). ``iban``/``couleur``
    left out of the body are unchanged.
    """
    compte = _owned_treasury(session, ctx.association_id, compte_id)

    if body.nom is not None:
        nom = body.nom.strip()
        if not nom:
            raise _bad_request("Le nom du compte ne peut pas être vide.")
        compte.libelle = nom
    if body.type_tresorerie is not None:
        compte.type_tresorerie = body.type_tresorerie
    if body.iban is not None:
        compte.iban = body.iban or None
    if body.couleur is not None:
        compte.couleur = body.couleur or None
    if body.ordre is not None:
        compte.ordre = body.ordre
    if body.is_active is not None:
        compte.is_active = body.is_active

    session.add(compte)
    record_audit(
        session,
        association_id=ctx.association_id,
        actor_user_id=ctx.user.id,
        action=AuditAction.COMPTE_TRESORERIE_UPDATE,
        target_type="compte",
        target_id=compte.id,
        detail=f"{compte.numero} {compte.libelle}",
    )
    session.commit()
    session.refresh(compte)

    solde = _treasury_soldes(session, ctx.association_id, [compte.id]).get(
        compte.id, ZERO
    )
    return _to_read(compte, solde)
