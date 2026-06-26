"""Change-password: policy, current-password check and session revocation."""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from database import get_session
from main import _fastapi_app as app

OLD = "password123"
NEW = "newpassword456"


@pytest.fixture(autouse=True)
def _use_test_session(session: Session):
    app.dependency_overrides[get_session] = lambda: session
    yield
    app.dependency_overrides.clear()


def _client() -> TestClient:
    return TestClient(app)


def _register(client: TestClient, email: str, password: str = OLD) -> None:
    resp = client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "name": "User"},
    )
    assert resp.status_code == 201, resp.text


def _login(client: TestClient, email: str, password: str) -> int:
    return client.post(
        "/api/auth/login", json={"email": email, "password": password}
    ).status_code


def test_change_password_succeeds_and_rotates_credentials():
    a = _client()
    _register(a, "u@example.com")
    _login(a, "u@example.com", OLD)

    resp = a.post(
        "/api/auth/change-password",
        json={"current_password": OLD, "new_password": NEW},
    )
    assert resp.status_code == 200, resp.text

    # The new password authenticates, the old one no longer does.
    assert _login(_client(), "u@example.com", NEW) == 200
    assert _login(_client(), "u@example.com", OLD) == 401


def test_change_password_revokes_other_sessions_but_keeps_current():
    a = _client()
    _register(a, "u@example.com")
    _login(a, "u@example.com", OLD)

    # A second device for the same user.
    b = _client()
    _login(b, "u@example.com", OLD)

    a.post(
        "/api/auth/change-password",
        json={"current_password": OLD, "new_password": NEW},
    )

    # The other device's refresh session was revoked…
    assert b.post("/api/auth/refresh").status_code == 401
    # …while the current device got a fresh session and still works.
    assert a.post("/api/auth/refresh").status_code == 200


def test_change_password_requires_correct_current_password():
    a = _client()
    _register(a, "u@example.com")
    _login(a, "u@example.com", OLD)

    resp = a.post(
        "/api/auth/change-password",
        json={"current_password": "wrong-password", "new_password": NEW},
    )
    assert resp.status_code == 400


def test_change_password_enforces_policy():
    a = _client()
    _register(a, "u@example.com")
    _login(a, "u@example.com", OLD)

    resp = a.post(
        "/api/auth/change-password",
        json={"current_password": OLD, "new_password": "short"},
    )
    assert resp.status_code == 400


def test_change_password_requires_authentication():
    resp = _client().post(
        "/api/auth/change-password",
        json={"current_password": OLD, "new_password": NEW},
    )
    assert resp.status_code == 401
