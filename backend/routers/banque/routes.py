"""Bank import & reconciliation endpoints (§5 Banque).

Import a CSV statement onto a treasury account, then reconcile each line: lettrer
it to an existing entry, create the missing entry from it, undo a lettrage, or set
a line aside. Import/reconcile are gated by ``BANK_RECONCILE``; creating an entry
from a line additionally requires ``ENTRY_CREATE_SIMPLE`` (it books an entry).
"""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlmodel import Session, asc, desc, select

from audit import AuditAction, record_audit
from auth_context import AccessContext, require_permission
from authz import Permission
from banque import ColumnMapping, ReleveParseError, parse_releve_csv, parse_releve_ofx
from database import get_session
from file_storage import MAX_UPLOAD_BYTES
from models import (
    EcritureDetailRead,
    ImportReleve,
    ImportReleveRead,
    LigneBancaire,
    LigneBancaireRead,
    LigneBancaireStatut,
    RapprochementCompteRead,
    RapprochementSuggestion,
)
from routers.ecritures.resolution import _require

from . import service
from .schemas import CreerEcritureRequest, RapprocherRequest

router = APIRouter(prefix="/api/asso/{association_id}", tags=["banque"])


def _decode(data: bytes) -> str:
    """Decode statement bytes, tolerating the two encodings French banks emit."""
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Fichier illisible (encodage non reconnu).",
    )


def _read_upload(fichier: UploadFile) -> bytes:
    """Read the uploaded file, hard-capped so a huge upload cannot blow up memory."""
    data = fichier.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Fichier trop volumineux.",
        )
    return data


def _finalize_import(session, ctx, compte, filename, lignes, default_name):
    """Persist the parsed rows (deduped) and record the audit, then commit."""
    if not lignes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucune ligne exploitable dans le fichier.",
        )
    releve = service.persist_import(
        session, ctx, compte, filename or default_name, lignes
    )
    record_audit(
        session,
        association_id=ctx.association_id,
        actor_user_id=ctx.user.id,
        action=AuditAction.RELEVE_IMPORT,
        target_type="import_releve",
        target_id=releve.id,
        detail=f"{releve.nb_lignes} lignes — {compte.libelle}",
    )
    session.commit()
    session.refresh(releve)
    return releve


# --- Import ---------------------------------------------------------------


@router.post(
    "/banque/import",
    response_model=ImportReleveRead,
    status_code=status.HTTP_201_CREATED,
)
def importer_releve(
    compte_id: str = Form(...),
    date_col: int = Form(...),
    libelle_col: int = Form(...),
    montant_col: int | None = Form(None),
    debit_col: int | None = Form(None),
    credit_col: int | None = Form(None),
    date_format: str = Form("%d/%m/%Y"),
    decimal_sep: str = Form(","),
    delimiter: str = Form(";"),
    has_header: bool = Form(True),
    fichier: UploadFile = File(...),
    ctx: AccessContext = Depends(require_permission(Permission.BANK_RECONCILE)),
    session: Session = Depends(get_session),
):
    """Import a CSV statement onto one of the association's treasury accounts."""
    compte = service.owned_treasury(session, ctx.association_id, compte_id)
    text = _decode(_read_upload(fichier))

    mapping = ColumnMapping(
        date=date_col,
        libelle=libelle_col,
        montant=montant_col,
        debit=debit_col,
        credit=credit_col,
        date_format=date_format,
        decimal_sep=decimal_sep,
        delimiter=delimiter,
        has_header=has_header,
    )
    try:
        lignes = parse_releve_csv(text, mapping)
    except ReleveParseError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from None

    filename = (fichier.filename or "releve.csv")[:200]
    return _finalize_import(session, ctx, compte, filename, lignes, "releve.csv")


@router.post(
    "/banque/import/ofx",
    response_model=ImportReleveRead,
    status_code=status.HTTP_201_CREATED,
)
def importer_releve_ofx(
    compte_id: str = Form(...),
    fichier: UploadFile = File(...),
    ctx: AccessContext = Depends(require_permission(Permission.BANK_RECONCILE)),
    session: Session = Depends(get_session),
):
    """Import an OFX statement (1.x/2.x) — self-describing, no column mapping.

    Movements already imported for the account (same FITID) are skipped, so
    re-importing an overlapping statement never books a duplicate.
    """
    compte = service.owned_treasury(session, ctx.association_id, compte_id)
    try:
        lignes = parse_releve_ofx(_read_upload(fichier))
    except ReleveParseError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from None

    filename = (fichier.filename or "releve.ofx")[:200]
    return _finalize_import(session, ctx, compte, filename, lignes, "releve.ofx")


@router.get("/banque/imports", response_model=list[ImportReleveRead])
def list_imports(
    compte_id: str | None = None,
    ctx: AccessContext = Depends(require_permission(Permission.BANK_RECONCILE)),
    session: Session = Depends(get_session),
):
    statement = select(ImportReleve).where(
        ImportReleve.association_id == ctx.association_id
    )
    if compte_id is not None:
        statement = statement.where(ImportReleve.compte_id == compte_id)
    statement = statement.order_by(desc(ImportReleve.created_at))
    return session.exec(statement).all()


@router.delete("/banque/imports/{import_id}", status_code=status.HTTP_204_NO_CONTENT)
def supprimer_import(
    import_id: str,
    ctx: AccessContext = Depends(require_permission(Permission.BANK_RECONCILE)),
    session: Session = Depends(get_session),
):
    """Delete an import and its statement lines; reconciled entries are untouched."""
    releve = service.owned_import(session, ctx.association_id, import_id)
    for ligne in session.exec(
        select(LigneBancaire).where(
            LigneBancaire.association_id == ctx.association_id,
            LigneBancaire.import_id == releve.id,
        )
    ).all():
        session.delete(ligne)
    record_audit(
        session,
        association_id=ctx.association_id,
        actor_user_id=ctx.user.id,
        action=AuditAction.RELEVE_DELETE,
        target_type="import_releve",
        target_id=releve.id,
    )
    session.delete(releve)
    session.commit()


# --- Reconciliation -------------------------------------------------------


@router.get("/banque/rapprochement", response_model=list[RapprochementCompteRead])
def etat_rapprochement(
    ctx: AccessContext = Depends(require_permission(Permission.REPORT_VIEW)),
    session: Session = Depends(get_session),
):
    """Per-account reconciliation state, for the Comptes page (C25).

    A read-only restitution — counts and totals, no statement content — so it sits
    behind ``REPORT_VIEW`` and stays visible to a président/CA who never touches
    the bank screens.
    """
    return service.etat_rapprochement(session, ctx.association_id)


@router.get("/banque/lignes", response_model=list[LigneBancaireRead])
def list_lignes(
    compte_id: str | None = None,
    import_id: str | None = None,
    statut: LigneBancaireStatut | None = None,
    ctx: AccessContext = Depends(require_permission(Permission.BANK_RECONCILE)),
    session: Session = Depends(get_session),
):
    """Statement lines of the association, oldest first, optionally filtered."""
    statement = select(LigneBancaire).where(
        LigneBancaire.association_id == ctx.association_id
    )
    if compte_id is not None:
        statement = statement.where(LigneBancaire.compte_id == compte_id)
    if import_id is not None:
        statement = statement.where(LigneBancaire.import_id == import_id)
    if statut is not None:
        statement = statement.where(LigneBancaire.statut == statut)
    statement = statement.order_by(
        asc(LigneBancaire.date_operation), asc(LigneBancaire.id)
    )
    return session.exec(statement).all()


@router.get(
    "/banque/lignes/{ligne_id}/suggestions",
    response_model=list[RapprochementSuggestion],
)
def suggestions_ligne(
    ligne_id: str,
    ctx: AccessContext = Depends(require_permission(Permission.BANK_RECONCILE)),
    session: Session = Depends(get_session),
):
    ligne = service.owned_ligne(session, ctx.association_id, ligne_id)
    return service.suggestions(session, ctx, ligne)


@router.post("/banque/lignes/{ligne_id}/rapprocher", response_model=LigneBancaireRead)
def rapprocher_ligne(
    ligne_id: str,
    body: RapprocherRequest,
    ctx: AccessContext = Depends(require_permission(Permission.BANK_RECONCILE)),
    session: Session = Depends(get_session),
):
    ligne = service.owned_ligne(session, ctx.association_id, ligne_id)
    ligne = service.rapprocher(session, ctx, ligne, body.ecriture_id)
    record_audit(
        session,
        association_id=ctx.association_id,
        actor_user_id=ctx.user.id,
        action=AuditAction.LIGNE_BANCAIRE_RAPPROCHE,
        target_type="ligne_bancaire",
        target_id=ligne.id,
        detail=f"écriture {body.ecriture_id}",
    )
    session.commit()
    session.refresh(ligne)
    return ligne


@router.post(
    "/banque/lignes/{ligne_id}/creer-ecriture",
    response_model=EcritureDetailRead,
    status_code=status.HTTP_201_CREATED,
)
def creer_ecriture_depuis_ligne(
    ligne_id: str,
    body: CreerEcritureRequest,
    ctx: AccessContext = Depends(require_permission(Permission.BANK_RECONCILE)),
    session: Session = Depends(get_session),
):
    """Create the missing entry from a statement line, then lettrer the line to it."""
    _require(ctx, Permission.ENTRY_CREATE_SIMPLE)  # booking an entry
    ligne = service.owned_ligne(session, ctx.association_id, ligne_id)
    ecriture = service.creer_ecriture(
        session,
        ctx,
        ligne,
        body.categorie_id,
        evenement_id=body.evenement_id,
        tiers_id=body.tiers_id,
        reference_externe=body.reference_externe,
        mode_reglement=body.mode_reglement,
    )
    record_audit(
        session,
        association_id=ctx.association_id,
        actor_user_id=ctx.user.id,
        action=AuditAction.ECRITURE_CREATE_SIMPLE,
        target_type="ecriture",
        target_id=ecriture.id,
        detail=f"depuis relevé — pièce {ecriture.numero_piece}",
    )
    record_audit(
        session,
        association_id=ctx.association_id,
        actor_user_id=ctx.user.id,
        action=AuditAction.LIGNE_BANCAIRE_RAPPROCHE,
        target_type="ligne_bancaire",
        target_id=ligne.id,
    )
    session.commit()
    session.refresh(ecriture)
    return ecriture


@router.post("/banque/lignes/{ligne_id}/delettrer", response_model=LigneBancaireRead)
def delettrer_ligne(
    ligne_id: str,
    ctx: AccessContext = Depends(require_permission(Permission.BANK_RECONCILE)),
    session: Session = Depends(get_session),
):
    ligne = service.owned_ligne(session, ctx.association_id, ligne_id)
    ligne = service.delettrer(session, ctx, ligne)
    record_audit(
        session,
        association_id=ctx.association_id,
        actor_user_id=ctx.user.id,
        action=AuditAction.LIGNE_BANCAIRE_DELETTRAGE,
        target_type="ligne_bancaire",
        target_id=ligne.id,
    )
    session.commit()
    session.refresh(ligne)
    return ligne


@router.post("/banque/lignes/{ligne_id}/ignorer", response_model=LigneBancaireRead)
def ignorer_ligne(
    ligne_id: str,
    ignore: bool = True,
    ctx: AccessContext = Depends(require_permission(Permission.BANK_RECONCILE)),
    session: Session = Depends(get_session),
):
    """Set a line aside (``ignore=true``) or bring it back (``ignore=false``)."""
    ligne = service.owned_ligne(session, ctx.association_id, ligne_id)
    ligne = service.ignorer(session, ligne, ignore)
    session.commit()
    session.refresh(ligne)
    return ligne
