"""Log retention.

LogEntry grows unbounded; purge entries older than LOG_RETENTION_DAYS.
Set LOG_RETENTION_DAYS=0 to disable purging.
"""

import os
from datetime import UTC, datetime, timedelta

from sqlmodel import Session, delete

from models import LogEntry

LOG_RETENTION_DAYS = int(os.getenv("LOG_RETENTION_DAYS", "90"))


def purge_old_logs(session: Session, retention_days: int | None = None) -> int:
    """Delete log entries older than the retention window; return the count."""
    days = LOG_RETENTION_DAYS if retention_days is None else retention_days
    if days <= 0:
        return 0
    # Timestamps are stored as naive UTC, so compare against a naive UTC cutoff.
    cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days)
    result = session.exec(delete(LogEntry).where(LogEntry.timestamp < cutoff))
    session.commit()
    return result.rowcount or 0
