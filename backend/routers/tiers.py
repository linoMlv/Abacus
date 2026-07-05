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
from auth_context import (
    AccessContext,
    get_active_membership,
    owned_or_404,
    require_permission,
)
from authz import Permission
from database import get_session
from models import Tiers, TiersRead, TypeTiers

router = APIRouter(prefix="/api/asso/{association_id}", tags=["tiers"])


class CreateTiersRequest(SQLModel):
    nom: str
    type: TypeTiers
    adresse: str | None = None
    code_postal: str | None = None
    ville: str | None = None


class UpdateTiersRequest(SQLModel):
    nom: str | None = None
    type: TypeTiers | None = None
    adresse: str | None = None
    code_postal: str | None = None
    ville: str | None = None
    is_active: bool | None = None


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

    tiers = Tiers(
        association_id=ctx.association_id,
        type=body.type,
        nom=nom,
        adresse=(body.adresse or "").strip() or None,
        code_postal=(body.code_postal or "").strip() or None,
        ville=(body.ville or "").strip() or None,
    )
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


@router.patch("/tiers/{tiers_id}", response_model=TiersRead)
def update_tiers(
    tiers_id: str,
    body: UpdateTiersRequest,
    ctx: AccessContext = Depends(require_permission(Permission.TIERS_MANAGE)),
    session: Session = Depends(get_session),
):
    """Edit a tiers (name/type/address, deactivate). Address feeds a donor receipt."""
    tiers = owned_or_404(
        session, Tiers, tiers_id, ctx.association_id, "Tiers introuvable"
    )

    if body.nom is not None:
        nom = body.nom.strip()
        if not nom:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Le nom est obligatoire.",
            )
        clash = session.exec(
            select(Tiers).where(
                Tiers.association_id == ctx.association_id,
                Tiers.nom == nom,
                Tiers.id != tiers.id,
            )
        ).first()
        if clash is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Un tiers porte déjà ce nom.",
            )
        tiers.nom = nom
    if body.type is not None:
        tiers.type = body.type
    if body.is_active is not None:
        tiers.is_active = body.is_active
    for field in ("adresse", "code_postal", "ville"):
        if field in body.model_fields_set:
            value = getattr(body, field)
            setattr(tiers, field, (value or "").strip() or None)

    session.add(tiers)
    record_audit(
        session,
        association_id=ctx.association_id,
        actor_user_id=ctx.user.id,
        action=AuditAction.TIERS_UPDATE,
        target_type="tiers",
        target_id=tiers.id,
        detail=tiers.nom,
    )
    session.commit()
    session.refresh(tiers)
    return tiers
