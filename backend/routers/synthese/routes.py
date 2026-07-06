"""The single consolidated dashboard endpoint."""

from datetime import date

from fastapi import APIRouter, Depends
from sqlmodel import Session

from auth_context import AccessContext, require_permission
from authz import Permission
from database import get_session
from models import SyntheseRead

from . import service

router = APIRouter(prefix="/api/asso/{association_id}", tags=["synthese"])


@router.get("/synthese", response_model=SyntheseRead)
def get_synthese(
    date_from: date | None = None,
    date_to: date | None = None,
    ctx: AccessContext = Depends(require_permission(Permission.DASHBOARD_VIEW)),
    session: Session = Depends(get_session),
):
    """Consolidated dashboard for the active association over an optional period.

    With no dates, the period defaults to the open fiscal year (else the calendar
    year). Treasury balances and alerts are read separately; everything here is
    re-derived from the ledger, scoped to ``ctx.association_id``.
    """
    default_from, default_to = service.default_range(session, ctx.association_id)
    date_from = date_from or default_from
    date_to = date_to or default_to
    aid = ctx.association_id

    return SyntheseRead(
        date_from=date_from,
        date_to=date_to,
        resultat=service.resultat(session, aid, date_from, date_to),
        repartition_categories=service.repartition_categories(
            session, aid, date_from, date_to
        ),
        repartition_evenements=service.repartition_evenements(
            session, aid, date_from, date_to
        ),
        courbe_tresorerie=service.courbe_tresorerie(session, aid, date_from, date_to),
        alertes=service.alertes(session, aid),
        budget=service.budget_synthese(session, aid, date_from),
    )
