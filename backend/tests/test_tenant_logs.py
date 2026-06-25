"""Per-tenant logs: path extraction, admin-scoped reading, RBAC and isolation."""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from database import get_session
from main import _fastapi_app as app
from middleware import _association_id_from_path
from models import LogEntry, Membership, Role

PASSWORD = "password123"


@pytest.fixture(autouse=True)
def _use_test_session(session: Session):
    app.dependency_overrides[get_session] = lambda: session
    yield
    app.dependency_overrides.clear()


def _client() -> TestClient:
    return TestClient(app)


def _register(client: TestClient, email: str) -> str:
    resp = client.post(
        "/api/auth/register",
        json={"email": email, "password": PASSWORD, "name": "User"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _login(client: TestClient, email: str) -> None:
    resp = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text


def _admin_with_association(
    email: str, name: str, assoc_email: str
) -> tuple[TestClient, str]:
    client = _client()
    _register(client, email)
    _login(client, email)
    resp = client.post(
        "/api/auth/associations", json={"name": name, "email": assoc_email}
    )
    assert resp.status_code == 201, resp.text
    return client, resp.json()["id"]


def _add_log(session: Session, association_id: str | None, **kwargs) -> None:
    session.add(
        LogEntry(
            method=kwargs.get("method", "GET"),
            path=kwargs.get("path", "/api/asso/x/members"),
            status_code=kwargs.get("status_code", 200),
            association_id=association_id,
            event_type=kwargs.get("event_type", "request"),
        )
    )
    session.commit()


# --------------------------------------------------------------------------- #
# Path extraction (pure)
# --------------------------------------------------------------------------- #
def test_association_id_extracted_from_scoped_path():
    assert _association_id_from_path("/api/asso/abc123/members") == "abc123"
    assert _association_id_from_path("/api/asso/abc123") == "abc123"


def test_no_association_id_for_non_scoped_paths():
    assert _association_id_from_path("/api/login") is None
    assert _association_id_from_path("/api/auth/session") is None
    assert _association_id_from_path("/api/asso/") is None
    assert _association_id_from_path("/health") is None


# --------------------------------------------------------------------------- #
# Scoped logs endpoint
# --------------------------------------------------------------------------- #
def test_admin_reads_only_own_association_logs(session: Session):
    admin, assoc_id = _admin_with_association(
        "admin@example.com", "Asso A", "a@example.com"
    )
    _add_log(session, assoc_id, event_type="request", path="/api/asso/a/members")
    _add_log(session, assoc_id, event_type="login", path="/api/asso/a/x")
    _add_log(session, "other-asso", path="/api/asso/other/members")
    _add_log(session, None, path="/api/login")  # global, no association

    logs = admin.get(f"/api/asso/{assoc_id}/logs")
    assert logs.status_code == 200
    body = logs.json()
    assert len(body) == 2
    assert all(entry["association_id"] == assoc_id for entry in body)


def test_scoped_logs_can_be_filtered(session: Session):
    admin, assoc_id = _admin_with_association(
        "admin@example.com", "Asso A", "a@example.com"
    )
    _add_log(session, assoc_id, event_type="login", path="/api/asso/a/login")
    _add_log(session, assoc_id, event_type="request", path="/api/asso/a/members")

    only_login = admin.get(
        f"/api/asso/{assoc_id}/logs", params={"event_type": "login"}
    ).json()
    assert [e["event_type"] for e in only_login] == ["login"]

    by_search = admin.get(
        f"/api/asso/{assoc_id}/logs", params={"search": "members"}
    ).json()
    assert [e["path"] for e in by_search] == ["/api/asso/a/members"]


def test_non_admin_cannot_read_logs(session: Session):
    admin, assoc_id = _admin_with_association(
        "admin@example.com", "Asso A", "a@example.com"
    )
    treasurer = _client()
    treasurer_id = _register(treasurer, "treasurer@example.com")
    _login(treasurer, "treasurer@example.com")
    session.add(
        Membership(user_id=treasurer_id, association_id=assoc_id, role=Role.TREASURER)
    )
    session.commit()

    assert treasurer.get(f"/api/asso/{assoc_id}/logs").status_code == 403


def test_cannot_read_another_associations_logs(session: Session):
    admin_a, _ = _admin_with_association("a@example.com", "A", "aa@example.com")
    _, assoc_b = _admin_with_association("b@example.com", "B", "bb@example.com")
    _add_log(session, assoc_b, path="/api/asso/b/members")

    # Admin of A is not a member of B -> scoped route hides it (404).
    assert admin_a.get(f"/api/asso/{assoc_b}/logs").status_code == 404
