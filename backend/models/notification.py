import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from .common import utcnow


class NotificationType(str, Enum):
    """What a notification is about. Stable strings (persisted)."""

    ECRITURE_A_VALIDER = "ecriture_a_valider"
    EXERCICE_A_CLOTURER = "exercice_a_cloturer"
    BUDGET_DEPASSE = "budget_depasse"
    EVENEMENT_DEPASSE = "evenement_depasse"
    BANQUE_A_RAPPROCHER = "banque_a_rapprocher"
    # Sent by the instance operator (Lot 6) — never derived from the books.
    BROADCAST = "broadcast"


class Notification(SQLModel, table=True):
    """One thing that awaits *one* person in *one* association (C28).

    Derived notifications carry a ``cle`` naming their subject ("ecriture:<id>"),
    which is what makes the sync idempotent: the same pending draft never rings
    twice, and once the draft is validated the row is cleared. A broadcast has no
    subject to settle, so it carries no ``cle`` and is never pruned.
    """

    __tablename__ = "notification"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "association_id", "cle", name="uq_notification_cle"
        ),
    )

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    association_id: str = Field(foreign_key="association.id", index=True)
    user_id: str = Field(foreign_key="user.id", index=True)  # the recipient
    type: NotificationType
    titre: str
    message: str | None = None
    lien: str | None = None  # in-app path, relative to the association
    cle: str | None = Field(default=None, index=True)  # subject key (null = broadcast)
    lu_at: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow)


class NotificationRead(SQLModel):
    id: str
    type: NotificationType
    titre: str
    message: str | None
    lien: str | None
    lu_at: datetime | None
    created_at: datetime


class NotificationsRead(SQLModel):
    """The bell: what awaits the caller, and how much of it is still unread."""

    notifications: list[NotificationRead]
    non_lues: int
