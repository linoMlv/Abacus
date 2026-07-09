"""Per-account brute-force lockout on the login endpoint.

After LOGIN_MAX_ATTEMPTS consecutive failures the account is locked: even the
correct password is refused (429) until the lockout expires. A successful login
clears the accumulated failed-attempt state. Independent of the per-IP limiter
(disabled in the suite), so the two defences compose.
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from database import get_session
from main import _fastapi_app as app
from models import User
from routers.identity.helpers import LOGIN_MAX_ATTEMPTS, _utcnow

PASSWORD = "password123"


@pytest.fixture(autouse=True)
def _use_test_session(session: Session):
    app.dependency_overrides[get_session] = lambda: session
    yield
    app.dependency_overrides.clear()


def _client() -> TestClient:
    return TestClient(app)


def _register(client: TestClient, email: str) -> None:
    assert (
        client.post(
            "/api/auth/register",
            json={"email": email, "password": PASSWORD, "name": "U"},
        ).status_code
        == 201
    )


def _login(client: TestClient, email: str, password: str):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def test_account_locks_after_repeated_failures(session: Session):
    client = _client()
    _register(client, "lock@example.com")

    # One short of the threshold: still plain 401s, not locked yet.
    for _ in range(LOGIN_MAX_ATTEMPTS - 1):
        assert _login(client, "lock@example.com", "wrong").status_code == 401

    # The threshold failure locks the account.
    assert _login(client, "lock@example.com", "wrong").status_code == 401

    # Now even the *correct* password is refused while locked.
    assert _login(client, "lock@example.com", PASSWORD).status_code == 429

    user = session.exec(select(User).where(User.email == "lock@example.com")).first()
    assert user.locked_until is not None


def test_login_succeeds_and_resets_after_lockout_expires(session: Session):
    client = _client()
    _register(client, "expire@example.com")
    for _ in range(LOGIN_MAX_ATTEMPTS):
        _login(client, "expire@example.com", "wrong")

    # Simulate the lockout window elapsing.
    user = session.exec(select(User).where(User.email == "expire@example.com")).first()
    user.locked_until = _utcnow().replace(year=_utcnow().year - 1)
    session.add(user)
    session.commit()

    assert _login(client, "expire@example.com", PASSWORD).status_code == 200

    session.refresh(user)
    assert user.locked_until is None
    assert user.failed_login_count == 0


def test_successful_login_clears_partial_failures(session: Session):
    client = _client()
    _register(client, "partial@example.com")
    _login(client, "partial@example.com", "wrong")
    _login(client, "partial@example.com", "wrong")

    assert _login(client, "partial@example.com", PASSWORD).status_code == 200
    user = session.exec(select(User).where(User.email == "partial@example.com")).first()
    assert user.failed_login_count == 0
