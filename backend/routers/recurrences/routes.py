"""Recurring-entry endpoints (§5 Récurrences).

CRUD a recurring simple-entry template plus a manual "generate due now" trigger
(the daily scheduler calls the same engine). All gated by ``RECURRENCE_MANAGE``
and tenant-scoped; generation reuses the assisted-entry builder, so a generated
entry is an ordinary saisie_simple linked back to its recurrence.
"""

from datetime import date

from fastapi import APIRouter, Depends, status
from sqlmodel import Session, asc, select

from audit import AuditAction, record_audit
from auth_context import AccessContext, require_permission
from authz import Permission
from database import get_session
from models import GenerationResult, Recurrence, RecurrenceRead
from recurrence_engine import generate_due

from . import service
from .schemas import RecurrenceCreate, RecurrenceUpdate

router = APIRouter(prefix="/api/asso/{association_id}", tags=["recurrences"])

_GUARD = require_permission(Permission.RECURRENCE_MANAGE)


@router.get("/recurrences", response_model=list[RecurrenceRead])
def list_recurrences(
    actif: bool | None = None,
    ctx: AccessContext = Depends(_GUARD),
    session: Session = Depends(get_session),
):
    statement = select(Recurrence).where(
        Recurrence.association_id == ctx.association_id
    )
    if actif is not None:
        statement = statement.where(Recurrence.actif == actif)
    statement = statement.order_by(asc(Recurrence.prochaine_echeance))
    return session.exec(statement).all()


@router.post(
    "/recurrences",
    response_model=RecurrenceRead,
    status_code=status.HTTP_201_CREATED,
)
def creer_recurrence(
    body: RecurrenceCreate,
    ctx: AccessContext = Depends(_GUARD),
    session: Session = Depends(get_session),
):
    categorie = service.resolve_categorie(
        session, ctx.association_id, body.categorie_id
    )
    compte = service.resolve_compte_tresorerie(
        session, ctx.association_id, body.compte_tresorerie_id
    )
    service.check_dates(body.prochaine_echeance, body.date_fin)

    recurrence = Recurrence(
        association_id=ctx.association_id,
        libelle=(body.libelle or "").strip() or categorie.libelle,
        categorie_id=categorie.id,
        compte_tresorerie_id=compte.id,
        montant=service.clean_montant(body.montant),
        tiers_id=service.resolve_tiers_id(session, ctx.association_id, body.tiers_id),
        evenement_id=service.resolve_evenement_id(
            session, ctx.association_id, body.evenement_id
        ),
        reference_externe=body.reference_externe,
        mode_reglement=body.mode_reglement,
        periodicite=body.periodicite,
        prochaine_echeance=body.prochaine_echeance,
        date_fin=body.date_fin,
        mode=body.mode,
        created_by=ctx.user.id,
    )
    session.add(recurrence)
    record_audit(
        session,
        association_id=ctx.association_id,
        actor_user_id=ctx.user.id,
        action=AuditAction.RECURRENCE_CREATE,
        target_type="recurrence",
        target_id=recurrence.id,
        detail=recurrence.libelle,
    )
    session.commit()
    session.refresh(recurrence)
    return recurrence


@router.patch("/recurrences/{recurrence_id}", response_model=RecurrenceRead)
def modifier_recurrence(
    recurrence_id: str,
    body: RecurrenceUpdate,
    ctx: AccessContext = Depends(_GUARD),
    session: Session = Depends(get_session),
):
    recurrence = service.owned_recurrence(session, ctx.association_id, recurrence_id)
    data = body.model_dump(exclude_unset=True)

    if "categorie_id" in data:
        recurrence.categorie_id = service.resolve_categorie(
            session, ctx.association_id, data["categorie_id"]
        ).id
    if "compte_tresorerie_id" in data:
        recurrence.compte_tresorerie_id = service.resolve_compte_tresorerie(
            session, ctx.association_id, data["compte_tresorerie_id"]
        ).id
    if "tiers_id" in data:
        recurrence.tiers_id = service.resolve_tiers_id(
            session, ctx.association_id, data["tiers_id"]
        )
    if "evenement_id" in data:
        recurrence.evenement_id = service.resolve_evenement_id(
            session, ctx.association_id, data["evenement_id"]
        )
    if "montant" in data:
        recurrence.montant = service.clean_montant(data["montant"])
    for field in (
        "libelle",
        "periodicite",
        "prochaine_echeance",
        "date_fin",
        "mode",
        "actif",
        "reference_externe",
        "mode_reglement",
    ):
        if field in data:
            setattr(recurrence, field, data[field])
    service.check_dates(recurrence.prochaine_echeance, recurrence.date_fin)

    session.add(recurrence)
    record_audit(
        session,
        association_id=ctx.association_id,
        actor_user_id=ctx.user.id,
        action=AuditAction.RECURRENCE_UPDATE,
        target_type="recurrence",
        target_id=recurrence.id,
    )
    session.commit()
    session.refresh(recurrence)
    return recurrence


@router.delete("/recurrences/{recurrence_id}", status_code=status.HTTP_204_NO_CONTENT)
def supprimer_recurrence(
    recurrence_id: str,
    ctx: AccessContext = Depends(_GUARD),
    session: Session = Depends(get_session),
):
    """Delete a recurrence; entries already generated from it are untouched."""
    recurrence = service.owned_recurrence(session, ctx.association_id, recurrence_id)
    record_audit(
        session,
        association_id=ctx.association_id,
        actor_user_id=ctx.user.id,
        action=AuditAction.RECURRENCE_DELETE,
        target_type="recurrence",
        target_id=recurrence.id,
    )
    session.delete(recurrence)
    session.commit()


@router.post("/recurrences/generer", response_model=GenerationResult)
def generer_echeances(
    ctx: AccessContext = Depends(_GUARD),
    session: Session = Depends(get_session),
):
    """Book every occurrence due today for this association (idempotent)."""
    generees = generate_due(
        session, today=date.today(), association_id=ctx.association_id
    )
    if generees:
        record_audit(
            session,
            association_id=ctx.association_id,
            actor_user_id=ctx.user.id,
            action=AuditAction.RECURRENCE_GENERATE,
            target_type="recurrence",
            target_id=None,
            detail=f"{generees} écriture(s)",
        )
    session.commit()
    return GenerationResult(generees=generees)
