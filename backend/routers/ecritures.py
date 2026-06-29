"""Accounting entries: assisted (simple) and manual creation, read, validation.

Every reference coming from the client (category, account, journal, entry id) is
re-resolved against the active association before use — an id is never trusted
to authorize access. Validated entries are immutable and entries can only be
booked into an *open* fiscal year covering their date.
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import selectinload
from sqlmodel import Session, SQLModel, desc, select

from accounting_engine import (
    EntryError,
    build_ecriture_extourne,
    build_ecriture_simple,
    build_ecriture_virement,
    find_open_exercice,
    next_numero_piece,
    validate_lignes,
)
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
    CategorieSaisie,
    Compte,
    Ecriture,
    EcritureDetailRead,
    EcritureListItem,
    EcritureOrigine,
    EcritureStatut,
    Evenement,
    Exercice,
    Journal,
    LigneEcriture,
    ModeReglement,
    SensCategorie,
    Tiers,
)

router = APIRouter(prefix="/api/asso/{association_id}", tags=["ecritures"])

_FINANCIAL_CLASS = 5  # comptes de trésorerie (512 banque, 531 caisse, …)


class TypeOperationFilter(str, Enum):
    """Type-first journal filter (§15.3), the vocabulary a treasurer reasons with.

    ``recette`` / ``depense`` are derived from the entry's category sens; a
    ``virement`` from its origine. A manual entry carries no category, so it
    matches none of these three (it only shows when no type filter is set).
    """

    RECETTE = "recette"
    DEPENSE = "depense"
    VIREMENT = "virement"


def _type_operation_clause(types: list[TypeOperationFilter], ctx: AccessContext):
    """OR clause matching entries of any of the requested operation types.

    Virement is identified by its origine; recette/dépense by the sens of the
    entry's category (re-scoped to the active association). A manual entry has
    no category, so it matches neither recette nor dépense.
    """
    conditions = []
    sens_wanted = [
        SensCategorie.RECETTE
        if t is TypeOperationFilter.RECETTE
        else SensCategorie.DEPENSE
        for t in types
        if t is not TypeOperationFilter.VIREMENT
    ]
    if sens_wanted:
        conditions.append(
            Ecriture.categorie_id.in_(
                select(CategorieSaisie.id).where(
                    CategorieSaisie.association_id == ctx.association_id,
                    CategorieSaisie.sens.in_(sens_wanted),
                )
            )
        )
    if TypeOperationFilter.VIREMENT in types:
        conditions.append(Ecriture.origine == EcritureOrigine.VIREMENT)
    return or_(*conditions)


# --- Request schemas ------------------------------------------------------


class SaisieSimpleRequest(SQLModel):
    categorie_id: str
    compte_tresorerie_id: str
    montant: Decimal
    date: date
    libelle: str | None = None
    tiers_id: str | None = None
    evenement_id: str | None = None
    reference_externe: str | None = None
    mode_reglement: ModeReglement | None = None


class VirementRequest(SQLModel):
    compte_source_id: str
    compte_destination_id: str
    montant: Decimal
    date: date
    libelle: str | None = None
    reference_externe: str | None = None
    mode_reglement: ModeReglement | None = None


class LigneInput(SQLModel):
    compte_id: str
    libelle: str | None = None
    debit: Decimal = Decimal("0")
    credit: Decimal = Decimal("0")


class SaisieManuelleRequest(SQLModel):
    journal_id: str
    date: date
    libelle: str
    lignes: list[LigneInput]
    tiers_id: str | None = None
    evenement_id: str | None = None
    reference_externe: str | None = None
    mode_reglement: ModeReglement | None = None


class EcritureContenu(SQLModel):
    """Origine-specific entry content; exactly one variant must be set.

    Reused by draft edition (``PATCH``) and contre-passation replacement: the
    variant provided must match the entry's origine, so the same builder/validation
    path produces the lines whatever the write path.
    """

    simple: SaisieSimpleRequest | None = None
    virement: VirementRequest | None = None
    manuelle: SaisieManuelleRequest | None = None


class ContrepassationRequest(SQLModel):
    """Optional corrected entry to book alongside the reversal (annule-et-remplace)."""

    remplacement: EcritureContenu | None = None


class ContrepassationRead(SQLModel):
    """The reversal (always) and, for annule-et-remplace, the corrected entry."""

    extourne: EcritureDetailRead
    remplacement: EcritureDetailRead | None = None


class BulkIdsRequest(SQLModel):
    ids: list[str]


class BulkIgnore(SQLModel):
    id: str
    raison: str


class BulkResult(SQLModel):
    """Outcome of a best-effort bulk action: processed ids and ignored ones."""

    traitees: list[str]
    ignorees: list[BulkIgnore]


# Origine ↔ the permission that authorizes creating/editing that kind of entry.
_CONTENU_PERMISSION = {
    EcritureOrigine.SAISIE_SIMPLE: Permission.ENTRY_CREATE_SIMPLE,
    EcritureOrigine.VIREMENT: Permission.ENTRY_CREATE_TRANSFER,
    EcritureOrigine.MANUELLE: Permission.ENTRY_CREATE_MANUAL,
}

# Origine ↔ the audit action recorded when an entry of that kind is created.
_CREATE_AUDIT = {
    EcritureOrigine.SAISIE_SIMPLE: AuditAction.ECRITURE_CREATE_SIMPLE,
    EcritureOrigine.VIREMENT: AuditAction.ECRITURE_CREATE_VIREMENT,
    EcritureOrigine.MANUELLE: AuditAction.ECRITURE_CREATE_MANUAL,
}


# --- Tenant-scoped resolution helpers -------------------------------------


def _bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def _open_exercice(session: Session, association_id: str, jour: date) -> Exercice:
    exercice = find_open_exercice(session, association_id, jour)
    if exercice is None:
        raise _bad_request("Aucun exercice ouvert ne couvre cette date.")
    return exercice


def _owned_compte(session: Session, association_id: str, compte_id: str) -> Compte:
    compte = session.exec(
        select(Compte).where(
            Compte.id == compte_id,
            Compte.association_id == association_id,
            Compte.is_active.is_(True),
        )
    ).first()
    if compte is None:
        raise _bad_request("Compte introuvable ou inactif.")
    return compte


def _owned_journal(session: Session, association_id: str, journal_id: str) -> Journal:
    journal = session.exec(
        select(Journal).where(
            Journal.id == journal_id, Journal.association_id == association_id
        )
    ).first()
    if journal is None:
        raise _bad_request("Journal introuvable.")
    return journal


def _owned_treasury(session: Session, association_id: str, compte_id: str) -> Compte:
    """Resolve an active *treasury* account of the association (else 400)."""
    compte = _owned_compte(session, association_id, compte_id)
    if compte.type_tresorerie is None:
        raise _bad_request("Le compte sélectionné n'est pas un compte de trésorerie.")
    return compte


def _resolve_tiers_id(
    session: Session, association_id: str, tiers_id: str | None
) -> str | None:
    """Validate an optional tiers reference belongs to the association (else 400)."""
    if tiers_id is None:
        return None
    tiers = session.exec(
        select(Tiers).where(
            Tiers.id == tiers_id,
            Tiers.association_id == association_id,
            Tiers.is_active.is_(True),
        )
    ).first()
    if tiers is None:
        raise _bad_request("Tiers introuvable ou inactif.")
    return tiers.id


def _resolve_evenement_id(
    session: Session, association_id: str, evenement_id: str | None
) -> str | None:
    """Validate an optional event reference belongs to the association (else 400)."""
    if evenement_id is None:
        return None
    evenement = session.exec(
        select(Evenement).where(
            Evenement.id == evenement_id,
            Evenement.association_id == association_id,
        )
    ).first()
    if evenement is None:
        raise _bad_request("Événement introuvable.")
    return evenement.id


def _journal_by_code(session: Session, association_id: str, code: str) -> Journal:
    journal = session.exec(
        select(Journal).where(
            Journal.association_id == association_id, Journal.code == code
        )
    ).first()
    if journal is None:
        raise _bad_request(f"Journal {code} introuvable.")
    return journal


def _owned_ecriture(
    session: Session, association_id: str, ecriture_id: str
) -> Ecriture:
    return owned_or_404(
        session, Ecriture, ecriture_id, association_id, "Écriture introuvable"
    )


def _audit_ecriture(
    session: Session,
    ctx: AccessContext,
    action: AuditAction,
    ecriture: Ecriture,
) -> None:
    """Record an audit entry for an action on ``ecriture`` (no commit)."""
    record_audit(
        session,
        association_id=ctx.association_id,
        actor_user_id=ctx.user.id,
        action=action,
        target_type="ecriture",
        target_id=ecriture.id,
        detail=f"pièce {ecriture.numero_piece}",
    )


# --- Entry builders (shared by creation, edition and replacement) ---------
#
# Each returns an unsaved ``Ecriture`` (lignes attached, balance-validated) for a
# single voucher number; the caller owns auditing and the transaction. Sharing
# them keeps creation, brouillon edition and contre-passation replacement in
# lockstep — one resolution/validation path per origine, no drift.


def _build_simple_entry(
    session: Session, ctx: AccessContext, body: SaisieSimpleRequest, numero_piece: int
) -> Ecriture:
    categorie = session.exec(
        select(CategorieSaisie).where(
            CategorieSaisie.id == body.categorie_id,
            CategorieSaisie.association_id == ctx.association_id,
            CategorieSaisie.is_active.is_(True),
        )
    ).first()
    if categorie is None:
        raise _bad_request("Catégorie introuvable ou inactive.")

    compte_tresorerie = _owned_compte(
        session, ctx.association_id, body.compte_tresorerie_id
    )
    if compte_tresorerie.classe != _FINANCIAL_CLASS:
        raise _bad_request(
            "Le compte de contrepartie doit être un compte de trésorerie (classe 5)."
        )

    exercice = _open_exercice(session, ctx.association_id, body.date)
    libelle = (body.libelle or "").strip() or categorie.libelle.strip()

    try:
        ecriture = build_ecriture_simple(
            association_id=ctx.association_id,
            exercice_id=exercice.id,
            journal_id=categorie.journal_id,
            compte_tresorerie_id=compte_tresorerie.id,
            compte_categorie_id=categorie.compte_id,
            sens=categorie.sens,
            montant=body.montant,
            date_ecriture=body.date,
            libelle=libelle,
            numero_piece=numero_piece,
            created_by=ctx.user.id,
        )
    except EntryError as exc:
        raise _bad_request(str(exc))

    ecriture.categorie_id = categorie.id  # remembered for "by category" views
    ecriture.tiers_id = _resolve_tiers_id(session, ctx.association_id, body.tiers_id)
    ecriture.evenement_id = _resolve_evenement_id(
        session, ctx.association_id, body.evenement_id
    )
    ecriture.reference_externe = body.reference_externe
    ecriture.mode_reglement = body.mode_reglement
    return ecriture


def _build_virement_entry(
    session: Session, ctx: AccessContext, body: VirementRequest, numero_piece: int
) -> Ecriture:
    source = _owned_treasury(session, ctx.association_id, body.compte_source_id)
    destination = _owned_treasury(
        session, ctx.association_id, body.compte_destination_id
    )
    journal = _journal_by_code(session, ctx.association_id, "OD")
    exercice = _open_exercice(session, ctx.association_id, body.date)
    libelle = (body.libelle or "").strip() or (
        f"Virement {source.libelle} → {destination.libelle}"
    )

    try:
        ecriture = build_ecriture_virement(
            association_id=ctx.association_id,
            exercice_id=exercice.id,
            journal_id=journal.id,
            compte_source_id=source.id,
            compte_destination_id=destination.id,
            montant=body.montant,
            date_ecriture=body.date,
            libelle=libelle,
            numero_piece=numero_piece,
            created_by=ctx.user.id,
        )
    except EntryError as exc:
        raise _bad_request(str(exc))

    ecriture.reference_externe = body.reference_externe
    ecriture.mode_reglement = body.mode_reglement
    return ecriture


def _build_manuelle_entry(
    session: Session, ctx: AccessContext, body: SaisieManuelleRequest, numero_piece: int
) -> Ecriture:
    journal = _owned_journal(session, ctx.association_id, body.journal_id)
    exercice = _open_exercice(session, ctx.association_id, body.date)

    # Resolve every referenced account in one query (vs. one round-trip per line),
    # then confirm each requested id is an active account of this association.
    requested_ids = {ligne.compte_id for ligne in body.lignes}
    valid_ids = (
        set(
            session.exec(
                select(Compte.id).where(
                    Compte.id.in_(requested_ids),
                    Compte.association_id == ctx.association_id,
                    Compte.is_active.is_(True),
                )
            ).all()
        )
        if requested_ids
        else set()
    )

    lignes: list[LigneEcriture] = []
    for ligne in body.lignes:
        if ligne.compte_id not in valid_ids:
            raise _bad_request("Compte introuvable ou inactif.")
        lignes.append(
            LigneEcriture(
                compte_id=ligne.compte_id,
                libelle=(ligne.libelle or body.libelle),
                debit=ligne.debit,
                credit=ligne.credit,
            )
        )

    try:
        validate_lignes(lignes)
    except EntryError as exc:
        raise _bad_request(str(exc))

    return Ecriture(
        association_id=ctx.association_id,
        exercice_id=exercice.id,
        journal_id=journal.id,
        date=body.date,
        numero_piece=numero_piece,
        libelle=body.libelle,
        tiers_id=_resolve_tiers_id(session, ctx.association_id, body.tiers_id),
        evenement_id=_resolve_evenement_id(
            session, ctx.association_id, body.evenement_id
        ),
        reference_externe=body.reference_externe,
        mode_reglement=body.mode_reglement,
        origine=EcritureOrigine.MANUELLE,
        created_by=ctx.user.id,
        lignes=lignes,
    )


def _require(ctx: AccessContext, permission: Permission) -> None:
    """Server-side permission check on the effective set (zero trust on the client)."""
    if permission not in ctx.permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
        )


def _resolve_contenu(contenu: EcritureContenu) -> tuple[EcritureOrigine, SQLModel]:
    """Return the single provided content variant as ``(origine, body)`` (else 400)."""
    variants = [
        (EcritureOrigine.SAISIE_SIMPLE, contenu.simple),
        (EcritureOrigine.VIREMENT, contenu.virement),
        (EcritureOrigine.MANUELLE, contenu.manuelle),
    ]
    provided = [(origine, body) for origine, body in variants if body is not None]
    if len(provided) != 1:
        raise _bad_request(
            "Fournir exactement une variante de contenu (simple, virement ou manuelle)."
        )
    return provided[0]


def _build_entry_from_contenu(
    session: Session,
    ctx: AccessContext,
    origine: EcritureOrigine,
    body: SQLModel,
    numero_piece: int,
) -> Ecriture:
    if origine is EcritureOrigine.SAISIE_SIMPLE:
        return _build_simple_entry(session, ctx, body, numero_piece)
    if origine is EcritureOrigine.VIREMENT:
        return _build_virement_entry(session, ctx, body, numero_piece)
    return _build_manuelle_entry(session, ctx, body, numero_piece)


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
    statement = select(Ecriture).where(Ecriture.association_id == ctx.association_id)
    if exercice_id is not None:
        statement = statement.where(Ecriture.exercice_id == exercice_id)
    if journal_id:
        statement = statement.where(Ecriture.journal_id.in_(journal_id))
    if compte_id:
        # Entries with at least one line on one of these accounts (e.g. treasury).
        statement = statement.where(
            Ecriture.id.in_(
                select(LigneEcriture.ecriture_id).where(
                    LigneEcriture.compte_id.in_(compte_id)
                )
            )
        )
    if type_operation:
        statement = statement.where(_type_operation_clause(type_operation, ctx))
    if categorie_id:
        statement = statement.where(Ecriture.categorie_id.in_(categorie_id))
    if tiers_id:
        statement = statement.where(Ecriture.tiers_id.in_(tiers_id))
    if evenement_id:
        statement = statement.where(Ecriture.evenement_id.in_(evenement_id))
    if date_from is not None:
        statement = statement.where(Ecriture.date >= date_from)
    if date_to is not None:
        statement = statement.where(Ecriture.date <= date_to)
    if statut:
        statement = statement.where(Ecriture.statut.in_(statut))
    if q:
        statement = statement.where(Ecriture.libelle.ilike(f"%{q}%"))
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


def _owned_ecritures(
    session: Session, association_id: str, ids: list[str]
) -> dict[str, Ecriture]:
    """Resolve the requested ids that belong to the association, keyed by id.

    A single tenant-scoped query; ids of another tenant (or unknown) are simply
    absent from the result, so the caller reports them as ignored (no leak).
    """
    if not ids:
        return {}
    rows = session.exec(
        select(Ecriture).where(
            Ecriture.id.in_(ids), Ecriture.association_id == association_id
        )
    ).all()
    return {e.id: e for e in rows}


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
