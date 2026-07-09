"""Strict RFC email validation on the write surfaces that persist an address."""

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


@pytest.mark.parametrize("bad", ["not-an-email", "a@", "@example.com", "a @b.com", ""])
def test_register_rejects_malformed_email(bad: str):
    resp = _client().post(
        "/api/auth/register",
        json={"email": bad, "password": PASSWORD, "name": "U"},
    )
    assert resp.status_code == 422


def test_register_accepts_a_valid_email():
    resp = _client().post(
        "/api/auth/register",
        json={"email": "valid@example.com", "password": PASSWORD, "name": "U"},
    )
    assert resp.status_code == 201


def _admin_with_association(client: TestClient, email: str, name: str) -> str:
    client.post(
        "/api/auth/register", json={"email": email, "password": PASSWORD, "name": "U"}
    )
    client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    resp = client.post(
        "/api/auth/associations", json={"name": name, "email": f"{name}@example.com"}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def test_association_creation_rejects_malformed_email():
    client = _client()
    client.post(
        "/api/auth/register",
        json={"email": "a@example.com", "password": PASSWORD, "name": "U"},
    )
    client.post(
        "/api/auth/login", json={"email": "a@example.com", "password": PASSWORD}
    )
    resp = client.post(
        "/api/auth/associations", json={"name": "alpha", "email": "bogus"}
    )
    assert resp.status_code == 422


def test_invitation_creation_rejects_malformed_email():
    client = _client()
    assoc = _admin_with_association(client, "admin@example.com", "alpha")
    resp = client.post(
        f"/api/asso/{assoc}/invitations",
        json={"email": "nope", "role": "treasurer"},
    )
    assert resp.status_code == 422
