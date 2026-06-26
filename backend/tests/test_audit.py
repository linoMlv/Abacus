"""Business audit trail: recording on entry actions, scoped admin read, RBAC."""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from database import get_session
from main import _fastapi_app as app
from models import Membership, Role

PASSWORD = "password123"
TODAY = "2026-06-27"


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
    assert (
        client.post(
            "/api/auth/login", json={"email": email, "password": PASSWORD}
        ).status_code
        == 200
    )


def _admin_with_association(email: str, name: str) -> tuple[TestClient, str, str]:
    client = _client()
    uid = _register(client, email)
    _login(client, email)
    resp = client.post(
        "/api/auth/associations", json={"name": name, "email": f"{name}@example.com"}
    )
    assert resp.status_code == 201, resp.text
    return client, resp.json()["id"], uid


def _member_client(
    session: Session, assoc_id: str, email: str, role: Role
) -> TestClient:
    client = _client()
    uid = _register(client, email)
    _login(client, email)
    session.add(Membership(user_id=uid, association_id=assoc_id, role=role))
    session.commit()
    return client


def _categorie_id(client: TestClient, assoc_id: str, libelle: str) -> str:
    cats = client.get(f"/api/asso/{assoc_id}/categories").json()
    return next(c["id"] for c in cats if c["libelle"] == libelle)


def _compte_id(client: TestClient, assoc_id: str, numero: str) -> str:
    comptes = client.get(
        f"/api/asso/{assoc_id}/comptes", params={"search": numero}
    ).json()
    return next(c["id"] for c in comptes if c["numero"] == numero)


def _post_simple(client: TestClient, assoc_id: str) -> str:
    resp = client.post(
        f"/api/asso/{assoc_id}/ecritures/simple",
        json={
            "categorie_id": _categorie_id(client, assoc_id, "Cotisations"),
            "compte_tresorerie_id": _compte_id(client, assoc_id, "512"),
            "montant": "50.00",
            "date": TODAY,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _audit(client: TestClient, assoc_id: str, **params) -> list[dict]:
    return client.get(f"/api/asso/{assoc_id}/audit", params=params).json()


# --- Recording ------------------------------------------------------------


def test_creating_an_entry_is_audited():
    admin, assoc, uid = _admin_with_association("admin@example.com", "alpha")
    entry = _post_simple(admin, assoc)

    rows = _audit(admin, assoc, action="ecriture.create_simple")
    assert len(rows) == 1
    assert rows[0]["target_type"] == "ecriture"
    assert rows[0]["target_id"] == entry
    assert rows[0]["actor_user_id"] == uid


def test_validation_and_deletion_are_audited():
    admin, assoc, _ = _admin_with_association("admin@example.com", "alpha")
    entry = _post_simple(admin, assoc)
    admin.post(f"/api/asso/{assoc}/ecritures/{entry}/validation")

    other = _post_simple(admin, assoc)
    admin.delete(f"/api/asso/{assoc}/ecritures/{other}")

    actions = {r["action"] for r in _audit(admin, assoc)}
    assert "ecriture.validate" in actions
    assert "ecriture.delete" in actions
    # Newest first.
    rows = _audit(admin, assoc)
    assert rows[0]["action"] == "ecriture.delete"


# --- Access control -------------------------------------------------------


def test_audit_read_requires_admin(session: Session):
    _, assoc, _ = _admin_with_association("admin@example.com", "alpha")
    treasurer = _member_client(session, assoc, "tres@example.com", Role.TREASURER)
    assert treasurer.get(f"/api/asso/{assoc}/audit").status_code == 403


def test_audit_is_tenant_isolated():
    admin_a, assoc_a, _ = _admin_with_association("a@example.com", "alpha")
    admin_b, assoc_b, _ = _admin_with_association("b@example.com", "beta")
    _post_simple(admin_a, assoc_a)

    # B's admin cannot read A's audit trail (not a member of A).
    assert admin_b.get(f"/api/asso/{assoc_a}/audit").status_code == 404
    # B's own trail does not contain A's actions.
    assert _audit(admin_b, assoc_b) == []


def test_audit_requires_authentication():
    assert _client().get("/api/asso/x/audit").status_code == 401
