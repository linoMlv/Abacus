"""Fiscal-year (exercice) lifecycle: listing, creation and closing.

Any active member may list the association's fiscal years (they are building
blocks of forms and reports). Opening a new year and closing one are structural
accounting acts, gated by :data:`Permission.EXERCISE_CLOSE`. Closing generates
the result-determination and report-à-nouveau entries and locks the year; it
lives in ``cloture.py`` and is exposed here.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, desc, select

from audit import AuditAction, record_audit
from auth_context import AccessContext, get_active_membership, require_permission
from authz import Permission
from database import get_session
from models import Exercice, ExerciceCreate, ExerciceRead

router = APIRouter(prefix="/api/asso/{association_id}", tags=["exercices"])


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


@router.post(
    "/exercices", response_model=ExerciceRead, status_code=status.HTTP_201_CREATED
)
def creer_exercice(
    body: ExerciceCreate,
    ctx: AccessContext = Depends(require_permission(Permission.EXERCISE_CLOSE)),
    session: Session = Depends(get_session),
):
    """Open a new fiscal year with parametric dates (shifted years supported).

    Guards: the label must be non-empty, the end must be strictly after the
    start, and the period must not overlap any existing exercice of the
    association (fiscal years partition time, so an entry maps to exactly one).
    """
    libelle = body.libelle.strip()
    if not libelle:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le libellé de l'exercice est obligatoire.",
        )
    if body.date_fin <= body.date_debut:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La date de fin doit être postérieure à la date de début.",
        )

    # Overlap: two ranges intersect iff each starts on or before the other ends.
    overlap = session.exec(
        select(Exercice.id).where(
            Exercice.association_id == ctx.association_id,
            Exercice.date_debut <= body.date_fin,
            Exercice.date_fin >= body.date_debut,
        )
    ).first()
    if overlap is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La période chevauche un exercice existant.",
        )

    exercice = Exercice(
        association_id=ctx.association_id,
        libelle=libelle,
        date_debut=body.date_debut,
        date_fin=body.date_fin,
    )
    session.add(exercice)
    record_audit(
        session,
        association_id=ctx.association_id,
        actor_user_id=ctx.user.id,
        action=AuditAction.EXERCICE_CREATE,
        target_type="exercice",
        target_id=exercice.id,
        detail=libelle,
    )
    session.commit()
    session.refresh(exercice)
    return exercice
