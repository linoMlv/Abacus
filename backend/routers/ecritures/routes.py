"""Accounting-entry endpoints: assisted (simple)/transfer/manual creation, read,
edition, validation, contre-passation and bulk actions.
"""

from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import selectinload
from sqlmodel import Session, desc, select

from accounting_engine import EntryError, build_ecriture_extourne, next_numero_piece
from accounting_filters import (
    JournalFilter,
    TypeOperationFilter,
    journal_filter_clauses,
)
from audit import AuditAction
from auth_context import AccessContext, get_active_membership, require_permission
from authz import Permission
from database import get_session
from models import (
    Ecriture,
    EcritureDetailRead,
    EcritureListItem,
    EcritureStatut,
    Exercice,
    ExerciceStatut,
    Journal,
    LigneEcriture,
)

from .builders import (
    _CONTENU_PERMISSION,
    _CREATE_AUDIT,
    _build_entry_from_contenu,
    _build_manuelle_entry,
    _build_simple_entry,
    _build_virement_entry,
    _resolve_contenu,
)
from .resolution import (
    _audit_ecriture,
    _bad_request,
    _owned_ecriture,
    _owned_ecritures,
    _require,
)
from .schemas import (
    BulkIdsRequest,
    BulkIgnore,
    BulkResult,
    ContrepassationRead,
    ContrepassationRequest,
    EcritureContenu,
    SaisieManuelleRequest,
    SaisieSimpleRequest,
    VirementRequest,
)

router = APIRouter(prefix="/api/asso/{association_id}", tags=["ecritures"])


# --- Creation -------------------------------------------------------------


@router.post(
    "/ecritures/simple",
    response_model=EcritureDetailRead,
    status_code=status.HTTP_201_CREATED,
)
def creer_saisie_simple(
    body: SaisieSimpleRequest,
    ctx: AccessContext = Depends(require_permission(Permission.ENTRY_CREATE_SIMPLE)),
    session: Session = Depends(get_session),
):
    ecriture = _build_simple_entry(
        session, ctx, body, next_numero_piece(session, ctx.association_id)
    )
    session.add(ecriture)
    _audit_ecriture(session, ctx, AuditAction.ECRITURE_CREATE_SIMPLE, ecriture)
    session.commit()
    session.refresh(ecriture)
    return ecriture


@router.post(
    "/ecritures/virement",
    response_model=EcritureDetailRead,
    status_code=status.HTTP_201_CREATED,
)
def creer_virement(
    body: VirementRequest,
    ctx: AccessContext = Depends(require_permission(Permission.ENTRY_CREATE_TRANSFER)),
    session: Session = Depends(get_session),
):
    """Internal transfer between two of the association's treasury accounts.

    Books a single balanced OD entry (D destination / C source) with no impact on
    the result. Both accounts are re-resolved against the active association and
    must be treasury accounts; an id from another tenant is rejected.
    """
    ecriture = _build_virement_entry(
        session, ctx, body, next_numero_piece(session, ctx.association_id)
    )
    session.add(ecriture)
    _audit_ecriture(session, ctx, AuditAction.ECRITURE_CREATE_VIREMENT, ecriture)
    session.commit()
    session.refresh(ecriture)
    return ecriture


@router.post(
    "/ecritures",
    response_model=EcritureDetailRead,
    status_code=status.HTTP_201_CREATED,
)
def creer_saisie_manuelle(
    body: SaisieManuelleRequest,
    ctx: AccessContext = Depends(require_permission(Permission.ENTRY_CREATE_MANUAL)),
    session: Session = Depends(get_session),
):
    ecriture = _build_manuelle_entry(
        session, ctx, body, next_numero_piece(session, ctx.association_id)
    )
    session.add(ecriture)
    _audit_ecriture(session, ctx, AuditAction.ECRITURE_CREATE_MANUAL, ecriture)
    session.commit()
    session.refresh(ecriture)
    return ecriture


# --- Read & lifecycle -----------------------------------------------------


@router.get("/ecritures", response_model=list[EcritureListItem])
def list_ecritures(
    exercice_id: str | None = None,
    journal_id: list[str] | None = Query(None),
    compte_id: list[str] | None = Query(None),
    type_operation: list[TypeOperationFilter] | None = Query(None),
    categorie_id: list[str] | None = Query(None),
    tiers_id: list[str] | None = Query(None),
    evenement_id: list[str] | None = Query(None),
    date_from: date | None = None,
    date_to: date | None = None,
    statut: list[EcritureStatut] | None = Query(None),
    q: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    ctx: AccessContext = Depends(require_permission(Permission.REPORT_VIEW)),
    session: Session = Depends(get_session),
):
    """The journal: entries of the active association, newest first.

    Every optional filter is applied on top of the mandatory ``association_id``
    scope and composes with the others (AND): an id from another tenant simply
    matches nothing, never widening access. The faceted filters (journal,
    ``compte_id`` — any account touched, e.g. a treasury account —, operation
    ``type_operation`` Recette/Dépense/Virement §15.3, category, tiers, event,
    statut) accept several values, each an OR *within* the facet. A ``date_from``/
    ``date_to`` range (inclusive) and a free-text libellé search complete them.
    Each row carries its total amount and journal code so the listing needs no
    per-row follow-up.
    """
    filtre = JournalFilter(
        journal_id=journal_id,
        compte_id=compte_id,
        type_operation=type_operation,
        categorie_id=categorie_id,
        tiers_id=tiers_id,
        evenement_id=evenement_id,
        date_from=date_from,
        date_to=date_to,
        statut=statut,
        q=q,
    )
    statement = select(Ecriture).where(
        Ecriture.association_id == ctx.association_id,
        *journal_filter_clauses(ctx.association_id, filtre),
    )
    if exercice_id is not None:
        statement = statement.where(Ecriture.exercice_id == exercice_id)
    statement = (
        statement.order_by(desc(Ecriture.date), desc(Ecriture.numero_piece))
        .limit(limit)
        .offset(offset)
        .options(selectinload(Ecriture.lignes))  # one extra query, no N+1
    )
    ecritures = session.exec(statement).all()

    # Journal codes resolved once for the (small) set of journals of the tenant.
    journal_codes = {
        j.id: j.code
        for j in session.exec(
            select(Journal).where(Journal.association_id == ctx.association_id)
        ).all()
    }
    return [
        EcritureListItem(
            id=e.id,
            exercice_id=e.exercice_id,
            journal_id=e.journal_id,
            categorie_id=e.categorie_id,
            date=e.date,
            numero_piece=e.numero_piece,
            libelle=e.libelle,
            tiers_id=e.tiers_id,
            evenement_id=e.evenement_id,
            reference_externe=e.reference_externe,
            mode_reglement=e.mode_reglement,
            statut=e.statut,
            origine=e.origine,
            extourne_de_id=e.extourne_de_id,
            created_at=e.created_at,
            validated_at=e.validated_at,
            montant=sum((ligne.debit for ligne in e.lignes), Decimal("0")),
            journal_code=journal_codes.get(e.journal_id, ""),
        )
        for e in ecritures
    ]


@router.get("/ecritures/{ecriture_id}", response_model=EcritureDetailRead)
def get_ecriture(
    ecriture_id: str,
    ctx: AccessContext = Depends(require_permission(Permission.REPORT_VIEW)),
    session: Session = Depends(get_session),
):
    return _owned_ecriture(session, ctx.association_id, ecriture_id)


@router.patch("/ecritures/{ecriture_id}", response_model=EcritureDetailRead)
def modifier_ecriture(
    ecriture_id: str,
    contenu: EcritureContenu,
    ctx: AccessContext = Depends(get_active_membership),
    session: Session = Depends(get_session),
):
    """Edit a *draft* entry: its content is rebuilt in place from ``contenu``.

    Only a brouillon is editable (a validated entry is immutable — correction goes
    through contre-passation, 409). The provided content variant must match the
    entry's origine, and editing requires that origine's create permission. The
    voucher number, id and creation metadata are preserved; the lines are rebuilt
    through the same balance-validated builder as creation.
    """
    original = _owned_ecriture(session, ctx.association_id, ecriture_id)
    if original.statut == EcritureStatut.VALIDEE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=("Une écriture validée est immuable (contre-passation requise)."),
        )

    origine, body = _resolve_contenu(contenu)
    if origine is not original.origine:
        raise _bad_request("Le type de contenu ne correspond pas à l'écriture.")
    _require(ctx, _CONTENU_PERMISSION[origine])

    built = _build_entry_from_contenu(
        session, ctx, origine, body, original.numero_piece
    )
    # Replace the content in place (keep id / numero_piece / created_at / created_by).
    # Clearing the collection lets the delete-orphan cascade remove the old lines.
    original.lignes.clear()
    session.flush()
    original.date = built.date
    original.libelle = built.libelle
    original.journal_id = built.journal_id
    original.exercice_id = built.exercice_id
    original.categorie_id = built.categorie_id
    original.tiers_id = built.tiers_id
    original.evenement_id = built.evenement_id
    original.reference_externe = built.reference_externe
    original.mode_reglement = built.mode_reglement
    session.add(original)
    for src in built.lignes:
        session.add(
            LigneEcriture(
                ecriture_id=original.id,
                compte_id=src.compte_id,
                libelle=src.libelle,
                debit=src.debit,
                credit=src.credit,
            )
        )
    _audit_ecriture(session, ctx, AuditAction.ECRITURE_UPDATE, original)
    session.commit()
    session.refresh(original)
    return original


@router.post("/ecritures/{ecriture_id}/validation", response_model=EcritureDetailRead)
def valider_ecriture(
    ecriture_id: str,
    ctx: AccessContext = Depends(require_permission(Permission.ENTRY_VALIDATE)),
    session: Session = Depends(get_session),
):
    ecriture = _owned_ecriture(session, ctx.association_id, ecriture_id)
    if ecriture.statut == EcritureStatut.VALIDEE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Écriture déjà validée."
        )

    ecriture.statut = EcritureStatut.VALIDEE
    ecriture.validated_by = ctx.user.id
    ecriture.validated_at = datetime.now(UTC)
    session.add(ecriture)
    _audit_ecriture(session, ctx, AuditAction.ECRITURE_VALIDATE, ecriture)
    session.commit()
    session.refresh(ecriture)
    return ecriture


@router.post(
    "/ecritures/{ecriture_id}/contrepassation",
    response_model=ContrepassationRead,
    status_code=status.HTTP_201_CREATED,
)
def contrepasser_ecriture(
    ecriture_id: str,
    body: ContrepassationRequest | None = None,
    ctx: AccessContext = Depends(require_permission(Permission.ENTRY_DELETE)),
    session: Session = Depends(get_session),
):
    """Contre-passe a validated entry; optionally book the corrected one in one call.

    The reversal (extourne) swaps the original's debit/credit, links back to it and
    lands as a brouillon to validate — the original is never touched (plan §10). A
    brouillon is not contre-passed (it is deleted, 409); an already-reversed entry
    is rejected (409). With ``remplacement`` (matching the original's origine), the
    corrected entry is also booked as a brouillon (annule-et-remplace), which extra
    requires that origine's create permission.
    """
    original = _owned_ecriture(session, ctx.association_id, ecriture_id)
    if original.statut != EcritureStatut.VALIDEE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Seule une écriture validée se contre-passe "
                "(un brouillon se supprime)."
            ),
        )
    # A closed year is locked: its entries cannot be corrected in place. Any
    # adjustment belongs to the open year (plan §6/§10).
    exercice = session.get(Exercice, original.exercice_id)
    if exercice is not None and exercice.statut == ExerciceStatut.CLOTURE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Exercice clôturé : l'écriture ne peut plus être contre-passée.",
        )
    already_reversed = session.exec(
        select(Ecriture.id).where(
            Ecriture.association_id == ctx.association_id,
            Ecriture.extourne_de_id == original.id,
        )
    ).first()
    if already_reversed is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Écriture déjà contre-passée.",
        )

    piece = next_numero_piece(session, ctx.association_id)
    try:
        extourne = build_ecriture_extourne(
            original=original, numero_piece=piece, created_by=ctx.user.id
        )
    except EntryError as exc:
        raise _bad_request(str(exc))
    session.add(extourne)
    _audit_ecriture(session, ctx, AuditAction.ECRITURE_CONTREPASSATION, original)

    remplacement_entry: Ecriture | None = None
    remplacement = body.remplacement if body is not None else None
    if remplacement is not None:
        origine, content = _resolve_contenu(remplacement)
        if origine is not original.origine:
            raise _bad_request(
                "Le remplacement doit être du même type que l'écriture d'origine."
            )
        _require(ctx, _CONTENU_PERMISSION[origine])
        remplacement_entry = _build_entry_from_contenu(
            session, ctx, origine, content, piece + 1
        )
        session.add(remplacement_entry)
        _audit_ecriture(session, ctx, _CREATE_AUDIT[origine], remplacement_entry)

    session.commit()
    session.refresh(extourne)
    if remplacement_entry is not None:
        session.refresh(remplacement_entry)
    return ContrepassationRead(extourne=extourne, remplacement=remplacement_entry)


@router.post("/ecritures/validation-groupee", response_model=BulkResult)
def valider_ecritures_groupe(
    body: BulkIdsRequest,
    ctx: AccessContext = Depends(require_permission(Permission.ENTRY_VALIDATE)),
    session: Session = Depends(get_session),
):
    """Validate several drafts at once (best-effort, per id).

    Each id is re-scoped to the association; an unknown/foreign id or an already
    validated entry is reported as ignored, never affecting another tenant.
    """
    owned = _owned_ecritures(session, ctx.association_id, body.ids)
    traitees: list[str] = []
    ignorees: list[BulkIgnore] = []
    now = datetime.now(UTC)
    for eid in dict.fromkeys(body.ids):  # de-dup, keep order
        ecriture = owned.get(eid)
        if ecriture is None:
            ignorees.append(BulkIgnore(id=eid, raison="Écriture introuvable."))
            continue
        if ecriture.statut == EcritureStatut.VALIDEE:
            ignorees.append(BulkIgnore(id=eid, raison="Déjà validée."))
            continue
        ecriture.statut = EcritureStatut.VALIDEE
        ecriture.validated_by = ctx.user.id
        ecriture.validated_at = now
        session.add(ecriture)
        _audit_ecriture(session, ctx, AuditAction.ECRITURE_VALIDATE, ecriture)
        traitees.append(eid)
    session.commit()
    return BulkResult(traitees=traitees, ignorees=ignorees)


@router.post("/ecritures/suppression-groupee", response_model=BulkResult)
def supprimer_ecritures_groupe(
    body: BulkIdsRequest,
    ctx: AccessContext = Depends(require_permission(Permission.ENTRY_DELETE)),
    session: Session = Depends(get_session),
):
    """Delete several drafts at once (best-effort, per id).

    A validated entry is kept and reported as ignored (it can only be reversed via
    contre-passation); an unknown/foreign id is likewise ignored, never touching
    another tenant.
    """
    owned = _owned_ecritures(session, ctx.association_id, body.ids)
    traitees: list[str] = []
    ignorees: list[BulkIgnore] = []
    for eid in dict.fromkeys(body.ids):  # de-dup, keep order
        ecriture = owned.get(eid)
        if ecriture is None:
            ignorees.append(BulkIgnore(id=eid, raison="Écriture introuvable."))
            continue
        if ecriture.statut == EcritureStatut.VALIDEE:
            ignorees.append(
                BulkIgnore(id=eid, raison="Validée (contre-passation requise).")
            )
            continue
        _audit_ecriture(session, ctx, AuditAction.ECRITURE_DELETE, ecriture)
        session.delete(ecriture)
        traitees.append(eid)
    session.commit()
    return BulkResult(traitees=traitees, ignorees=ignorees)


@router.delete("/ecritures/{ecriture_id}", status_code=status.HTTP_204_NO_CONTENT)
def supprimer_ecriture(
    ecriture_id: str,
    ctx: AccessContext = Depends(require_permission(Permission.ENTRY_DELETE)),
    session: Session = Depends(get_session),
):
    ecriture = _owned_ecriture(session, ctx.association_id, ecriture_id)
    if ecriture.statut == EcritureStatut.VALIDEE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Une écriture validée ne peut être supprimée "
                "(contre-passation requise)."
            ),
        )
    _audit_ecriture(session, ctx, AuditAction.ECRITURE_DELETE, ecriture)
    session.delete(ecriture)
    session.commit()
