"""Database-enforced model invariants (defence in depth)."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from models import RefreshSession


def _session(**owner) -> RefreshSession:
    return RefreshSession(
        token_hash=f"h-{owner}",
        expires_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(days=1),
        **owner,
    )


def test_refresh_session_accepts_a_single_owner(session: Session):
    session.add(_session(user_id="u1"))
    session.commit()  # user-owned: valid
    session.add(_session(association_id="a1"))
    session.commit()  # association-owned (legacy shape): valid


def test_refresh_session_rejects_no_owner(session: Session):
    session.add(_session())
    with pytest.raises(IntegrityError):
        session.commit()


def test_refresh_session_rejects_two_owners(session: Session):
    session.add(_session(user_id="u1", association_id="a1"))
    with pytest.raises(IntegrityError):
        session.commit()
