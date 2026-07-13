"""Read access to the accounting journals (tenant-scoped).

Any active member may consult them: they are form building blocks. The chart of
accounts and its restitutions (balance, grand livre) live in ``routers/comptes``;
fiscal years in ``routers/exercices``.
"""

from fastapi import APIRouter, Depends
from sqlmodel import Session, asc, select

from auth_context import AccessContext, get_active_membership
from database import get_session
from models import Journal, JournalRead

router = APIRouter(prefix="/api/asso/{association_id}", tags=["accounting"])


@router.get("/journaux", response_model=list[JournalRead])
def list_journaux(
    ctx: AccessContext = Depends(get_active_membership),
    session: Session = Depends(get_session),
):
    statement = (
        select(Journal)
        .where(Journal.association_id == ctx.association_id)
        .order_by(asc(Journal.code))
    )
    return session.exec(statement).all()
