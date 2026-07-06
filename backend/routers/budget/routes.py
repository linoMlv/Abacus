"""Budget endpoints: read the prévu/réalisé grid, upsert the prévu amounts."""

from fastapi import APIRouter, Depends
from sqlmodel import Session

from auth_context import AccessContext, require_permission
from authz import Permission
from database import get_session
from models import BudgetRead, BudgetUpsert

from . import service

router = APIRouter(prefix="/api/asso/{association_id}", tags=["budget"])


@router.get("/budget", response_model=BudgetRead)
def get_budget(
    exercice_id: str | None = None,
    ctx: AccessContext = Depends(require_permission(Permission.BUDGET_MANAGE)),
    session: Session = Depends(get_session),
):
    """Budget of an exercice (default = the open one): prévu, réalisé and écart."""
    exercice = service.resolve_exercice(session, ctx.association_id, exercice_id)
    return service.build_read(session, ctx.association_id, exercice)


@router.put("/budget", response_model=BudgetRead)
def put_budget(
    body: BudgetUpsert,
    ctx: AccessContext = Depends(require_permission(Permission.BUDGET_MANAGE)),
    session: Session = Depends(get_session),
):
    """Replace the exercice budget with the given prévu amounts (a full grid)."""
    return service.upsert(session, ctx.association_id, ctx.user.id, body)
