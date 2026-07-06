"""Document exports (T7): tenant-scoped PDF / Excel downloads.

Generation is server-side and streamed as an attachment (``nosniff``), like the
justificatifs download. These documents are the books, so reading requires the
``REPORT_VIEW`` consultation permission (revoking it denies the exports too);
every query is scoped to the active association and any id from the client is
re-checked via ``owned_or_404``.
"""

from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlmodel import Session, desc, select

from accounting_filters import JournalFilter, TypeOperationFilter
from auth_context import AccessContext, owned_or_404, require_permission
from authz import Permission
from database import get_session
from exports import documents
from exports.data import (
    annexe_data,
    bilan_data,
    budget_data,
    compte_resultat_data,
    evenement_bilan_data,
    grand_livre_data,
    journal_data,
    releve_data,
    resolve_period,
)
from exports.fec import FEC_MEDIA_TYPE, build_fec
from exports.xlsx import XLSX_MEDIA_TYPE
from models import Association, Compte, EcritureStatut, Evenement, Exercice
from routers.budget.service import resolve_exercice as resolve_budget_exercice

router = APIRouter(prefix="/api/asso/{association_id}", tags=["exports"])

PDF_MEDIA_TYPE = "application/pdf"


def _content_disposition(filename: str) -> str:
    """RFC 6266 attachment header (ASCII filename + UTF-8 form)."""
    ascii_name = filename.encode("ascii", "ignore").decode("ascii") or "export"
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"


def _file_response(content: bytes, filename: str, media_type: str) -> Response:
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": _content_disposition(filename),
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


def _association_name(session: Session, association_id: str) -> str:
    association = session.get(Association, association_id)
    return association.name if association else "Association"


def journal_filter_query(
    date_from: date | None = None,
    date_to: date | None = None,
    journal_id: list[str] | None = Query(None),
    compte_id: list[str] | None = Query(None),
    type_operation: list[TypeOperationFilter] | None = Query(None),
    categorie_id: list[str] | None = Query(None),
    tiers_id: list[str] | None = Query(None),
    evenement_id: list[str] | None = Query(None),
    statut: list[EcritureStatut] | None = Query(None),
    q: str | None = None,
) -> JournalFilter:
    """The journal export's faceted filter, mirroring ``GET /ecritures`` params."""
    return JournalFilter(
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


@router.get("/exports/tresorerie/{compte_id}/releve.pdf")
def export_releve_pdf(
    compte_id: str,
    date_from: date | None = None,
    date_to: date | None = None,
    ctx: AccessContext = Depends(require_permission(Permission.REPORT_VIEW)),
    session: Session = Depends(get_session),
):
    """Bank-statement-style PDF for one treasury account over a period."""
    compte = owned_or_404(
        session,
        Compte,
        compte_id,
        ctx.association_id,
        "Compte de trésorerie introuvable",
    )
    if compte.type_tresorerie is None:
        # Not a treasury account — reported as 404 (never reveal ordinary accounts).
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Compte de trésorerie introuvable",
        )
    df, dt = resolve_period(session, ctx.association_id, date_from, date_to)
    data = releve_data(session, ctx.association_id, compte, df, dt)
    pdf = documents.releve_pdf(_association_name(session, ctx.association_id), data)
    return _file_response(pdf, f"releve-{compte.numero}-{df}-{dt}.pdf", PDF_MEDIA_TYPE)


@router.get("/exports/journal.pdf")
def export_journal_pdf(
    filtre: JournalFilter = Depends(journal_filter_query),
    ctx: AccessContext = Depends(require_permission(Permission.REPORT_VIEW)),
    session: Session = Depends(get_session),
):
    df, dt = resolve_period(
        session, ctx.association_id, filtre.date_from, filtre.date_to
    )
    filtre.date_from, filtre.date_to = df, dt
    data = journal_data(session, ctx.association_id, filtre)
    pdf = documents.journal_pdf(_association_name(session, ctx.association_id), data)
    return _file_response(pdf, f"journal-{df}-{dt}.pdf", PDF_MEDIA_TYPE)


@router.get("/exports/journal.xlsx")
def export_journal_xlsx(
    filtre: JournalFilter = Depends(journal_filter_query),
    ctx: AccessContext = Depends(require_permission(Permission.REPORT_VIEW)),
    session: Session = Depends(get_session),
):
    df, dt = resolve_period(
        session, ctx.association_id, filtre.date_from, filtre.date_to
    )
    filtre.date_from, filtre.date_to = df, dt
    data = journal_data(session, ctx.association_id, filtre)
    return _file_response(
        documents.journal_xlsx(data), f"journal-{df}-{dt}.xlsx", XLSX_MEDIA_TYPE
    )


@router.get("/exports/grand-livre.pdf")
def export_grand_livre_pdf(
    date_from: date | None = None,
    date_to: date | None = None,
    ctx: AccessContext = Depends(require_permission(Permission.REPORT_VIEW)),
    session: Session = Depends(get_session),
):
    df, dt = resolve_period(session, ctx.association_id, date_from, date_to)
    data = grand_livre_data(session, ctx.association_id, df, dt)
    pdf = documents.grand_livre_pdf(
        _association_name(session, ctx.association_id), data
    )
    return _file_response(pdf, f"grand-livre-{df}-{dt}.pdf", PDF_MEDIA_TYPE)


@router.get("/exports/grand-livre.xlsx")
def export_grand_livre_xlsx(
    date_from: date | None = None,
    date_to: date | None = None,
    ctx: AccessContext = Depends(require_permission(Permission.REPORT_VIEW)),
    session: Session = Depends(get_session),
):
    df, dt = resolve_period(session, ctx.association_id, date_from, date_to)
    data = grand_livre_data(session, ctx.association_id, df, dt)
    return _file_response(
        documents.grand_livre_xlsx(data), f"grand-livre-{df}-{dt}.xlsx", XLSX_MEDIA_TYPE
    )


@router.get("/exports/compte-resultat.pdf")
def export_compte_resultat_pdf(
    date_from: date | None = None,
    date_to: date | None = None,
    ctx: AccessContext = Depends(require_permission(Permission.REPORT_VIEW)),
    session: Session = Depends(get_session),
):
    df, dt = resolve_period(session, ctx.association_id, date_from, date_to)
    data = compte_resultat_data(session, ctx.association_id, df, dt)
    pdf = documents.compte_resultat_pdf(
        _association_name(session, ctx.association_id), data
    )
    return _file_response(pdf, f"compte-resultat-{df}-{dt}.pdf", PDF_MEDIA_TYPE)


@router.get("/exports/bilan.pdf")
def export_bilan_pdf(
    date_to: date | None = None,
    ctx: AccessContext = Depends(require_permission(Permission.REPORT_VIEW)),
    session: Session = Depends(get_session),
):
    """Balance sheet as of ``date_to`` (defaults to the open exercice's end)."""
    _, dt = resolve_period(session, ctx.association_id, None, date_to)
    data = bilan_data(session, ctx.association_id, dt)
    pdf = documents.bilan_pdf(_association_name(session, ctx.association_id), data)
    return _file_response(pdf, f"bilan-{dt}.pdf", PDF_MEDIA_TYPE)


@router.get("/exports/annexe.pdf")
def export_annexe_pdf(
    date_to: date | None = None,
    ctx: AccessContext = Depends(require_permission(Permission.REPORT_VIEW)),
    session: Session = Depends(get_session),
):
    """Annexe ANC (computed tables) as of ``date_to`` (defaults to exercice end)."""
    _, dt = resolve_period(session, ctx.association_id, None, date_to)
    data = annexe_data(session, ctx.association_id, dt)
    pdf = documents.annexe_pdf(_association_name(session, ctx.association_id), data)
    return _file_response(pdf, f"annexe-{dt}.pdf", PDF_MEDIA_TYPE)


@router.get("/exports/evenements/{evenement_id}/bilan.pdf")
def export_evenement_bilan_pdf(
    evenement_id: str,
    ctx: AccessContext = Depends(require_permission(Permission.REPORT_VIEW)),
    session: Session = Depends(get_session),
):
    evenement = owned_or_404(
        session, Evenement, evenement_id, ctx.association_id, "Événement introuvable"
    )
    data = evenement_bilan_data(session, ctx.association_id, evenement)
    pdf = documents.evenement_bilan_pdf(
        _association_name(session, ctx.association_id), data
    )
    return _file_response(pdf, f"bilan-evenement-{evenement.nom}.pdf", PDF_MEDIA_TYPE)


@router.get("/exports/budget.pdf")
def export_budget_pdf(
    exercice_id: str | None = None,
    ctx: AccessContext = Depends(require_permission(Permission.BUDGET_MANAGE)),
    session: Session = Depends(get_session),
):
    """Budget (prévu/réalisé) of an exercice as PDF, gated by BUDGET_MANAGE."""
    exercice = resolve_budget_exercice(session, ctx.association_id, exercice_id)
    data = budget_data(session, ctx.association_id, exercice)
    pdf = documents.budget_pdf(_association_name(session, ctx.association_id), data)
    return _file_response(pdf, f"budget-{exercice.libelle}.pdf", PDF_MEDIA_TYPE)


@router.get("/exports/budget.xlsx")
def export_budget_xlsx(
    exercice_id: str | None = None,
    ctx: AccessContext = Depends(require_permission(Permission.BUDGET_MANAGE)),
    session: Session = Depends(get_session),
):
    """Budget (prévu/réalisé) of an exercice as Excel, gated by BUDGET_MANAGE."""
    exercice = resolve_budget_exercice(session, ctx.association_id, exercice_id)
    data = budget_data(session, ctx.association_id, exercice)
    return _file_response(
        documents.budget_xlsx(data), f"budget-{exercice.libelle}.xlsx", XLSX_MEDIA_TYPE
    )


def _resolve_exercice(session: Session, association_id: str, exercice_id: str | None):
    """The requested exercice (owned) or, by default, the most recent one."""
    if exercice_id:
        return owned_or_404(
            session, Exercice, exercice_id, association_id, "Exercice introuvable"
        )
    exercice = session.exec(
        select(Exercice)
        .where(Exercice.association_id == association_id)
        .order_by(desc(Exercice.date_debut))
    ).first()
    if exercice is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Aucun exercice."
        )
    return exercice


@router.get("/exports/fec")
def export_fec(
    exercice_id: str | None = None,
    ctx: AccessContext = Depends(require_permission(Permission.REPORT_EXPORT_FEC)),
    session: Session = Depends(get_session),
):
    """FEC of a fiscal year (validated entries), gated by REPORT_EXPORT_FEC."""
    exercice = _resolve_exercice(session, ctx.association_id, exercice_id)
    content = build_fec(session, ctx.association_id, exercice.id)
    return _file_response(content, f"FEC-{exercice.libelle}.txt", FEC_MEDIA_TYPE)
