"""Third parties (tiers): a lightweight, quick-addable directory (§15.3).

A tiers is who an operation is with — supplier, member/client, donor, funder.
In this step the module is intentionally small: list (for the saisie selector)
and quick-add. Every read/write is scoped to the active association; creation is
gated by ``TIERS_MANAGE`` (trésorier+), so a volunteer can add one on the fly
without breaking the gentle UX. The accounting third-party ledger (401/411,
lettrage) is a later concern.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, SQLModel, asc, select

from audit import AuditAction, record_audit
from auth_context import AccessContext, get_active_membership, require_permission
from authz import Permission
from database import get_session
from models import Tiers, TiersRead, TypeTiers

router = APIRouter(prefix="/api/asso/{association_id}", tags=["tiers"])


class CreateTiersRequest(SQLModel):
    nom: str
    type: TypeTiers


@router.get("/tiers", response_model=list[TiersRead])
def list_tiers(
    type: TypeTiers | None = None,
    include_inactive: bool = False,
    ctx: AccessContext = Depends(get_active_membership),
    session: Session = Depends(get_session),
):
    statement = select(Tiers).where(Tiers.association_id == ctx.association_id)
    if type is not None:
        statement = statement.where(Tiers.type == type)
    if not include_inactive:
        statement = statement.where(Tiers.is_active.is_(True))
    statement = statement.order_by(asc(Tiers.nom))
    return session.exec(statement).all()


@router.post("/tiers", response_model=TiersRead, status_code=status.HTTP_201_CREATED)
def creer_tiers(
    body: CreateTiersRequest,
    ctx: AccessContext = Depends(require_permission(Permission.TIERS_MANAGE)),
    session: Session = Depends(get_session),
):
    nom = body.nom.strip()
    if not nom:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Le nom est obligatoire."
        )

    exists = session.exec(
        select(Tiers).where(
            Tiers.association_id == ctx.association_id, Tiers.nom == nom
        )
    ).first()
    if exists is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Un tiers porte déjà ce nom.",
        )

    tiers = Tiers(association_id=ctx.association_id, type=body.type, nom=nom)
    session.add(tiers)
    record_audit(
        session,
        association_id=ctx.association_id,
        actor_user_id=ctx.user.id,
        action=AuditAction.TIERS_CREATE,
        target_type="tiers",
        target_id=tiers.id,
        detail=nom,
    )
    session.commit()
    session.refresh(tiers)
    return tiers
