"""Events (événements): an analytic axis tagging entries (§15.6).

An event groups the recettes/dépenses of an action/project so its result
(Σ produits − Σ charges on the tagged entries) can be tracked against an optional
budget. CRUD is gated by ``EVENT_MANAGE`` (trésorier+); any active member may
read. Every id from the client is re-scoped to the active association
(``owned_or_404`` / explicit ``association_id`` filter) before use.
"""

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlmodel import Session, SQLModel, asc, select

from accounting_engine import CENTS, ZERO, validated_only
from audit import AuditAction, record_audit
from auth_context import (
    AccessContext,
    get_active_membership,
    owned_or_404,
    require_permission,
)
from authz import Permission
from database import get_session
from models import (
    Compte,
    Ecriture,
    Evenement,
    EvenementRead,
    EvenementStatut,
    LigneEcriture,
)

router = APIRouter(prefix="/api/asso/{association_id}", tags=["evenements"])

# Income-statement classes: charges (6) and produits (7).
_CHARGE, _PRODUIT = 6, 7

# Fields a PATCH may set directly (None = left unchanged). ``nom`` is handled
# apart because it is trimmed and checked for uniqueness.
_UPDATABLE = (
    "description",
    "date_debut",
    "date_fin",
    "budget_recettes",
    "budget_depenses",
    "statut",
    "couleur",
)


class CreateEvenementRequest(SQLModel):
    nom: str
    description: str | None = None
    date_debut: date | None = None
    date_fin: date | None = None
    budget_recettes: Decimal | None = None
    budget_depenses: Decimal | None = None
    couleur: str | None = None


class UpdateEvenementRequest(SQLModel):
    nom: str | None = None
    description: str | None = None
    date_debut: date | None = None
    date_fin: date | None = None
    budget_recettes: Decimal | None = None
    budget_depenses: Decimal | None = None
    statut: EvenementStatut | None = None
    couleur: str | None = None


def _bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def _realise(
    session: Session, association_id: str
) -> dict[str, tuple[Decimal, Decimal]]:
    """Per event, the réalisé (produits cl.7, charges cl.6) of its tagged entries.

    Produits are credited (credit − debit on class 7), charges are debited
    (debit − credit on class 6). Computed in one grouped query for the whole
    association (no per-event round-trip).
    """
    rows = session.exec(
        select(
            Ecriture.evenement_id,
            Compte.classe,
            func.coalesce(func.sum(LigneEcriture.debit), 0),
            func.coalesce(func.sum(LigneEcriture.credit), 0),
        )
        .join(LigneEcriture, LigneEcriture.ecriture_id == Ecriture.id)
        .join(Compte, Compte.id == LigneEcriture.compte_id)
        .where(
            Ecriture.association_id == association_id,
            Ecriture.evenement_id.is_not(None),
            Compte.classe.in_([_CHARGE, _PRODUIT]),
            validated_only(),
        )
        .group_by(Ecriture.evenement_id, Compte.classe)
    ).all()
    out: dict[str, dict[str, Decimal]] = {}
    for evenement_id, classe, total_debit, total_credit in rows:
        debit = Decimal(str(total_debit))
        credit = Decimal(str(total_credit))
        acc = out.setdefault(evenement_id, {"recettes": ZERO, "depenses": ZERO})
        if classe == _PRODUIT:
            acc["recettes"] += credit - debit
        else:  # charge
            acc["depenses"] += debit - credit
    return {k: (v["recettes"], v["depenses"]) for k, v in out.items()}


def _to_read(
    evenement: Evenement, recettes: Decimal, depenses: Decimal
) -> EvenementRead:
    recettes = recettes.quantize(CENTS)
    depenses = depenses.quantize(CENTS)
    return EvenementRead(
        id=evenement.id,
        nom=evenement.nom,
        description=evenement.description,
        date_debut=evenement.date_debut,
        date_fin=evenement.date_fin,
        budget_recettes=evenement.budget_recettes,
        budget_depenses=evenement.budget_depenses,
        statut=evenement.statut,
        couleur=evenement.couleur,
        realise_recettes=recettes,
        realise_depenses=depenses,
        resultat=recettes - depenses,
    )


def _owned_evenement(
    session: Session, association_id: str, evenement_id: str
) -> Evenement:
    return owned_or_404(
        session, Evenement, evenement_id, association_id, "Événement introuvable"
    )


@router.get("/evenements", response_model=list[EvenementRead])
def list_evenements(
    statut: EvenementStatut | None = None,
    ctx: AccessContext = Depends(get_active_membership),
    session: Session = Depends(get_session),
):
    statement = select(Evenement).where(Evenement.association_id == ctx.association_id)
    if statut is not None:
        statement = statement.where(Evenement.statut == statut)
    evenements = session.exec(statement.order_by(asc(Evenement.nom))).all()
    realise = _realise(session, ctx.association_id)
    return [_to_read(e, *realise.get(e.id, (ZERO, ZERO))) for e in evenements]


@router.get("/evenements/{evenement_id}", response_model=EvenementRead)
def get_evenement(
    evenement_id: str,
    ctx: AccessContext = Depends(get_active_membership),
    session: Session = Depends(get_session),
):
    evenement = _owned_evenement(session, ctx.association_id, evenement_id)
    recettes, depenses = _realise(session, ctx.association_id).get(
        evenement.id, (ZERO, ZERO)
    )
    return _to_read(evenement, recettes, depenses)


@router.post("/evenements", response_model=EvenementRead, status_code=201)
def create_evenement(
    body: CreateEvenementRequest,
    ctx: AccessContext = Depends(require_permission(Permission.EVENT_MANAGE)),
    session: Session = Depends(get_session),
):
    nom = body.nom.strip()
    if not nom:
        raise _bad_request("Le nom de l'événement est requis.")
    if _name_taken(session, ctx.association_id, nom):
        raise _bad_request("Un événement portant ce nom existe déjà.")

    evenement = Evenement(
        association_id=ctx.association_id,
        nom=nom,
        description=body.description,
        date_debut=body.date_debut,
        date_fin=body.date_fin,
        budget_recettes=body.budget_recettes,
        budget_depenses=body.budget_depenses,
        couleur=body.couleur,
    )
    session.add(evenement)
    record_audit(
        session,
        association_id=ctx.association_id,
        actor_user_id=ctx.user.id,
        action=AuditAction.EVENEMENT_CREATE,
        target_type="evenement",
        target_id=evenement.id,
        detail=nom,
    )
    session.commit()
    session.refresh(evenement)
    return _to_read(evenement, ZERO, ZERO)


@router.patch("/evenements/{evenement_id}", response_model=EvenementRead)
def update_evenement(
    evenement_id: str,
    body: UpdateEvenementRequest,
    ctx: AccessContext = Depends(require_permission(Permission.EVENT_MANAGE)),
    session: Session = Depends(get_session),
):
    evenement = _owned_evenement(session, ctx.association_id, evenement_id)
    if body.nom is not None:
        nom = body.nom.strip()
        if not nom:
            raise _bad_request("Le nom de l'événement est requis.")
        if _name_taken(session, ctx.association_id, nom, exclude_id=evenement.id):
            raise _bad_request("Un événement portant ce nom existe déjà.")
        evenement.nom = nom
    for field in _UPDATABLE:
        value = getattr(body, field)
        if value is not None:
            setattr(evenement, field, value)

    session.add(evenement)
    record_audit(
        session,
        association_id=ctx.association_id,
        actor_user_id=ctx.user.id,
        action=AuditAction.EVENEMENT_UPDATE,
        target_type="evenement",
        target_id=evenement.id,
        detail=evenement.nom,
    )
    session.commit()
    session.refresh(evenement)
    recettes, depenses = _realise(session, ctx.association_id).get(
        evenement.id, (ZERO, ZERO)
    )
    return _to_read(evenement, recettes, depenses)


def _name_taken(
    session: Session, association_id: str, nom: str, exclude_id: str | None = None
) -> bool:
    statement = select(Evenement).where(
        Evenement.association_id == association_id, Evenement.nom == nom
    )
    if exclude_id is not None:
        statement = statement.where(Evenement.id != exclude_id)
    return session.exec(statement).first() is not None
