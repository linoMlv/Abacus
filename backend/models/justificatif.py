import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel

from .common import utcnow


class Justificatif(SQLModel, table=True):
    """A supporting document (invoice, receipt…) attached to an entry (§15.7).

    Metadata lives here; the bytes live behind a ``FileStorage`` (local volume
    today, S3/MinIO later) addressed by the server-generated ``storage_key``.
    The stored ``content_type`` is the one sniffed from the file, not the one
    the client declared.
    """

    __tablename__ = "justificatif"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    association_id: str = Field(foreign_key="association.id", index=True)
    ecriture_id: str | None = Field(default=None, foreign_key="ecriture.id", index=True)
    filename: str  # sanitized original name, for display/download only
    content_type: str  # canonical, sniffed from the bytes
    size: int
    storage_key: str = Field(unique=True, index=True)
    uploaded_by: str | None = Field(default=None, foreign_key="user.id")
    created_at: datetime = Field(default_factory=utcnow)


class JustificatifRead(SQLModel):
    id: str
    ecriture_id: str | None
    filename: str
    content_type: str
    size: int
    created_at: datetime
