"""The notification bell: read what awaits you, mark it read.

Every route is scoped to the active association *and* to the caller: a member only
ever sees — and only ever marks read — their own notifications.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlmodel import Session

from auth_context import AccessContext, get_active_membership, owned_or_404
from database import get_session
from http_errors import not_found
from models import Notification, NotificationRead, NotificationsRead

from . import service

router = APIRouter(prefix="/api/asso/{association_id}", tags=["notifications"])


@router.get("/notifications", response_model=NotificationsRead)
def list_notifications(
    ctx: AccessContext = Depends(get_active_membership),
    session: Session = Depends(get_session),
):
    """What awaits the caller — recomputed from the association's state, then read.

    Any member may call it: the *content* is already filtered by what they hold
    (a draft to validate only reaches whoever may validate one).
    """
    service.sync(session, ctx)
    notifications = service.list_for(session, ctx)
    return NotificationsRead(
        notifications=[
            NotificationRead.model_validate(n, from_attributes=True)
            for n in notifications
        ],
        non_lues=sum(1 for n in notifications if n.lu_at is None),
    )


@router.post("/notifications/lecture", status_code=200)
def mark_all_read(
    ctx: AccessContext = Depends(get_active_membership),
    session: Session = Depends(get_session),
):
    service.mark_all_read(session, ctx)
    return {"status": "ok"}


@router.post(
    "/notifications/{notification_id}/lecture", response_model=NotificationRead
)
def mark_read(
    notification_id: str,
    ctx: AccessContext = Depends(get_active_membership),
    session: Session = Depends(get_session),
):
    notification = owned_or_404(
        session,
        Notification,
        notification_id,
        ctx.association_id,
        "Notification introuvable",
    )
    # Same association is not enough: it must be *mine*. Reported as 404, so a
    # member cannot even probe whether a colleague's notification exists.
    if notification.user_id != ctx.user.id:
        raise not_found("Notification introuvable")

    if notification.lu_at is None:
        notification.lu_at = datetime.now(UTC)
        session.add(notification)
        session.commit()
        session.refresh(notification)
    return notification
