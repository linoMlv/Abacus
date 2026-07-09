"""Narrative-annexe endpoints (ANC comptes annuels).

Each exercice owns a list of free-text rubrics (the human commentary that
accompanies the computed annexe tables). Reading is gated by ``REPORT_VIEW``
(it is report content); writing by the dedicated ``ANNEXE_MANAGE``. Everything
is tenant-scoped: exercice and rubric ids are re-resolved against the active
association before use.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from audit import AuditAction, record_audit
from auth_context import AccessContext, require_permission
from authz import Permission
from database import get_session
from models import AnnexeRubrique, AnnexeRubriqueRead

from . import service
from .schemas import RubriqueCreate, RubriqueReorder, RubriqueUpdate

router = APIRouter(prefix="/api/asso/{association_id}", tags=["annexe"])


def _clean_titre(titre: str) -> str:
    titre = titre.strip()
    if not titre:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le titre de la rubrique est obligatoire.",
        )
    return titre


@router.get("/exercices/{exercice_id}/annexe", response_model=list[AnnexeRubriqueRead])
def list_annexe(
    exercice_id: str,
    ctx: AccessContext = Depends(require_permission(Permission.REPORT_VIEW)),
    session: Session = Depends(get_session),
):
    """The exercice's narrative rubrics, ordered (default ANC set seeded if empty)."""
    service.owned_exercice(session, ctx.association_id, exercice_id)
    return service.list_rubriques(session, ctx.association_id, exercice_id)


@router.post(
    "/exercices/{exercice_id}/annexe",
    response_model=AnnexeRubriqueRead,
    status_code=status.HTTP_201_CREATED,
)
def add_rubrique(
    exercice_id: str,
    body: RubriqueCreate,
    ctx: AccessContext = Depends(require_permission(Permission.ANNEXE_MANAGE)),
    session: Session = Depends(get_session),
):
    """Append a rubric to the exercice's annexe."""
    service.owned_exercice(session, ctx.association_id, exercice_id)
    rubrique = AnnexeRubrique(
        association_id=ctx.association_id,
        exercice_id=exercice_id,
        titre=_clean_titre(body.titre),
        contenu=body.contenu,
        ordre=service.next_ordre(session, ctx.association_id, exercice_id),
    )
    session.add(rubrique)
    _audit(session, ctx, exercice_id, f"ajout « {rubrique.titre} »")
    session.commit()
    session.refresh(rubrique)
    return rubrique


@router.patch("/annexe/{rubrique_id}", response_model=AnnexeRubriqueRead)
def update_rubrique(
    rubrique_id: str,
    body: RubriqueUpdate,
    ctx: AccessContext = Depends(require_permission(Permission.ANNEXE_MANAGE)),
    session: Session = Depends(get_session),
):
    """Edit a rubric's title and/or body."""
    rubrique = service.owned_rubrique(session, ctx.association_id, rubrique_id)
    if body.titre is not None:
        rubrique.titre = _clean_titre(body.titre)
    if body.contenu is not None:
        rubrique.contenu = body.contenu
    session.add(rubrique)
    _audit(session, ctx, rubrique.exercice_id, f"édition « {rubrique.titre} »")
    session.commit()
    session.refresh(rubrique)
    return rubrique


@router.delete("/annexe/{rubrique_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rubrique(
    rubrique_id: str,
    ctx: AccessContext = Depends(require_permission(Permission.ANNEXE_MANAGE)),
    session: Session = Depends(get_session),
):
    """Remove a rubric from the annexe."""
    rubrique = service.owned_rubrique(session, ctx.association_id, rubrique_id)
    exercice_id = rubrique.exercice_id
    titre = rubrique.titre
    session.delete(rubrique)
    _audit(session, ctx, exercice_id, f"suppression « {titre} »")
    session.commit()


@router.put(
    "/exercices/{exercice_id}/annexe/ordre",
    response_model=list[AnnexeRubriqueRead],
)
def reorder_rubriques(
    exercice_id: str,
    body: RubriqueReorder,
    ctx: AccessContext = Depends(require_permission(Permission.ANNEXE_MANAGE)),
    session: Session = Depends(get_session),
):
    """Set the display order from the given id list; unlisted rubrics keep the tail."""
    service.owned_exercice(session, ctx.association_id, exercice_id)
    rubriques = service.list_rubriques(session, ctx.association_id, exercice_id)
    by_id = {r.id: r for r in rubriques}
    # Provided ids that actually belong to this exercice, in order.
    ordered = [by_id[i] for i in body.ids if i in by_id]
    remaining = [r for r in rubriques if r.id not in {r2.id for r2 in ordered}]
    for ordre, rubrique in enumerate(ordered + remaining):
        rubrique.ordre = ordre
        session.add(rubrique)
    _audit(session, ctx, exercice_id, "réordonnancement")
    session.commit()
    return service.list_rubriques(session, ctx.association_id, exercice_id)


def _audit(session: Session, ctx: AccessContext, exercice_id: str, detail: str) -> None:
    record_audit(
        session,
        association_id=ctx.association_id,
        actor_user_id=ctx.user.id,
        action=AuditAction.ANNEXE_UPDATE,
        target_type="exercice",
        target_id=exercice_id,
        detail=detail,
    )
