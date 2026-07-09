"""User refresh-session tests: rotation, revocation and isolation from legacy.

A used refresh token must be single-use (rotated), logout/logout-all must
revoke server-side, and a legacy association refresh token must never be
accepted by the user refresh endpoint.
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from database import get_session
from main import _fastapi_app as app

PASSWORD = "password123"


@pytest.fixture(autouse=True)
def _use_test_session(session: Session):
    app.dependency_overrides[get_session] = lambda: session
    yield
    app.dependency_overrides.clear()


def _client() -> TestClient:
    return TestClient(app)


def _register(client: TestClient, email: str) -> None:
    resp = client.post(
        "/api/auth/register",
        json={"email": email, "password": PASSWORD, "name": "User"},
    )
    assert resp.status_code == 201, resp.text


def _login(client: TestClient, email: str):
    resp = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    return resp


def _refresh_cookie(resp) -> str:
    token = resp.cookies.get("refresh_token")
    assert token, "expected a refresh_token cookie"
    return token


def _replay_refresh(token: str):
    """POST /api/auth/refresh from a fresh client carrying only ``token``."""
    client = _client()
    client.cookies.set("refresh_token", token, domain="testserver", path="/")
    return client.post("/api/auth/refresh")


def test_login_issues_a_usable_refresh_session():
    client = _client()
    _register(client, "a@example.com")
    _login(client, "a@example.com")

    resp = client.post("/api/auth/refresh")
    assert resp.status_code == 200
    assert resp.json()["user"]["email"] == "a@example.com"


def test_refresh_rotates_and_old_token_is_revoked():
    client = _client()
    _register(client, "a@example.com")
    old = _refresh_cookie(_login(client, "a@example.com"))

    rotated = client.post("/api/auth/refresh")
    assert rotated.status_code == 200
    new = _refresh_cookie(rotated)
    assert new != old

    # Replaying the old (rotated-out) token must fail.
    assert _replay_refresh(old).status_code == 401


def test_refresh_without_cookie_is_401():
    assert _client().post("/api/auth/refresh").status_code == 401


def test_logout_revokes_the_refresh_session():
    client = _client()
    _register(client, "a@example.com")
    token = _refresh_cookie(_login(client, "a@example.com"))

    assert client.post("/api/auth/logout").status_code == 200

    # The captured token is revoked server-side, not merely cleared client-side.
    assert _replay_refresh(token).status_code == 401


def test_logout_all_revokes_every_session():
    _register(_client(), "shared@example.com")  # registration is idempotent-safe

    device1 = _client()
    token1 = _refresh_cookie(_login(device1, "shared@example.com"))
    device2 = _client()
    token2 = _refresh_cookie(_login(device2, "shared@example.com"))

    assert device1.post("/api/auth/logout-all").status_code == 200

    for token in (token1, token2):
        assert _replay_refresh(token).status_code == 401


def test_refresh_session_without_user_is_rejected(session: Session):
    """A refresh session not bound to a user (``user_id`` NULL) — e.g. a legacy
    association session — must never be accepted by the user refresh endpoint.

    Such a session carries an ``association_id`` instead (the owner-XOR invariant
    requires exactly one owner), which is exactly the legacy shape being refused.
    """
    from datetime import UTC, datetime, timedelta

    from models import Association, RefreshSession
    from security import generate_refresh_token, hash_refresh_token

    association = Association(name="legacy", email="legacy@example.com")
    session.add(association)
    session.commit()

    raw = generate_refresh_token()
    session.add(
        RefreshSession(
            user_id=None,
            association_id=association.id,
            token_hash=hash_refresh_token(raw),
            expires_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(days=1),
        )
    )
    session.commit()

    assert _replay_refresh(raw).status_code == 401
