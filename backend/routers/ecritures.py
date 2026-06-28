"""Accounting entries: assisted (simple) and manual creation, read, validation.

Every reference coming from the client (category, account, journal, entry id) is
re-resolved against the active association before use — an id is never trusted
to authorize access. Validated entries are immutable and entries can only be
booked into an *open* fiscal year covering their date.
"""

from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import selectinload
from sqlmodel import Session, SQLModel, desc, select

from accounting_engine import (
    EntryError,
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
    Exercice,
    Journal,
    LigneEcriture,
    ModeReglement,
)

router = APIRouter(prefix="/api/asso/{association_id}", tags=["ecritures"])

_FINANCIAL_CLASS = 5  # comptes de trésorerie (512 banque, 531 caisse, …)


# --- Request schemas ------------------------------------------------------


class SaisieSimpleRequest(SQLModel):
    categorie_id: str
    compte_tresorerie_id: str
    montant: Decimal
    date: date
    libelle: str | None = None
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
    reference_externe: str | None = None
    mode_reglement: ModeReglement | None = None


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
            numero_piece=next_numero_piece(session, ctx.association_id),
            created_by=ctx.user.id,
        )
    except EntryError as exc:
        raise _bad_request(str(exc))

    ecriture.categorie_id = categorie.id  # remembered for "by category" views
    ecriture.reference_externe = body.reference_externe
    ecriture.mode_reglement = body.mode_reglement
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
            numero_piece=next_numero_piece(session, ctx.association_id),
            created_by=ctx.user.id,
        )
    except EntryError as exc:
        raise _bad_request(str(exc))

    ecriture.reference_externe = body.reference_externe
    ecriture.mode_reglement = body.mode_reglement
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

    ecriture = Ecriture(
        association_id=ctx.association_id,
        exercice_id=exercice.id,
        journal_id=journal.id,
        date=body.date,
        numero_piece=next_numero_piece(session, ctx.association_id),
        libelle=body.libelle,
        reference_externe=body.reference_externe,
        mode_reglement=body.mode_reglement,
        origine=EcritureOrigine.MANUELLE,
        created_by=ctx.user.id,
        lignes=lignes,
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
    journal_id: str | None = None,
    compte_id: str | None = None,
    statut: EcritureStatut | None = None,
    q: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    ctx: AccessContext = Depends(get_active_membership),
    session: Session = Depends(get_session),
):
    """The journal: entries of the active association, newest first.

    The optional ``exercice_id`` / ``journal_id`` / ``compte_id`` (filter by
    treasury account or any account touched) are plain filters applied on top of
    the mandatory ``association_id`` scope — an id from another tenant simply
    matches nothing, it never widens access. Each row carries its total amount
    and journal code so the listing needs no per-row follow-up.
    """
    statement = select(Ecriture).where(Ecriture.association_id == ctx.association_id)
    if exercice_id is not None:
        statement = statement.where(Ecriture.exercice_id == exercice_id)
    if journal_id is not None:
        statement = statement.where(Ecriture.journal_id == journal_id)
    if compte_id is not None:
        # Entries with at least one line on this account (e.g. a treasury account).
        statement = statement.where(
            Ecriture.id.in_(
                select(LigneEcriture.ecriture_id).where(
                    LigneEcriture.compte_id == compte_id
                )
            )
        )
    if statut is not None:
        statement = statement.where(Ecriture.statut == statut)
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
            reference_externe=e.reference_externe,
            mode_reglement=e.mode_reglement,
            statut=e.statut,
            origine=e.origine,
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
    ctx: AccessContext = Depends(get_active_membership),
    session: Session = Depends(get_session),
):
    return _owned_ecriture(session, ctx.association_id, ecriture_id)


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
