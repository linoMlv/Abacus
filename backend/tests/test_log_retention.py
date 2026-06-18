from datetime import UTC, datetime, timedelta

from sqlmodel import Session, select

from log_retention import purge_old_logs
from models import LogEntry


def test_purge_removes_only_old_entries(session: Session):
    now = datetime.now(UTC).replace(tzinfo=None)
    old = LogEntry(method="GET", path="/old", timestamp=now - timedelta(days=120))
    recent = LogEntry(method="GET", path="/recent", timestamp=now - timedelta(days=10))
    session.add(old)
    session.add(recent)
    session.commit()

    deleted = purge_old_logs(session, retention_days=90)
    assert deleted == 1

    remaining = session.exec(select(LogEntry)).all()
    assert [e.path for e in remaining] == ["/recent"]


def test_purge_disabled_when_retention_zero(session: Session):
    now = datetime.now(UTC).replace(tzinfo=None)
    session.add(
        LogEntry(method="GET", path="/old", timestamp=now - timedelta(days=999))
    )
    session.commit()

    assert purge_old_logs(session, retention_days=0) == 0
    assert len(session.exec(select(LogEntry)).all()) == 1
