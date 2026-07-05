"""Association settings: VAT régime toggle (SETTINGS_MANAGE, admin)."""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from database import get_session
from main import _fastapi_app as app
from models import Membership, Role

PASSWORD = "password123"


@pytest.fixture(autouse=True)
def _use_test_session(session: Session):
    app.dependency_overrides[get_session] = lambda: session
    yield
    app.dependency_overrides.clear()


def _register_login(email: str) -> tuple[TestClient, str]:
    client = TestClient(app)
    reg = client.post(
        "/api/auth/register",
        json={"email": email, "password": PASSWORD, "name": "U"},
    )
    assert reg.status_code == 201, reg.text
    assert (
        client.post(
            "/api/auth/login", json={"email": email, "password": PASSWORD}
        ).status_code
        == 200
    )
    return client, reg.json()["id"]


def _admin_with_association(email: str, name: str) -> tuple[TestClient, str]:
    client, _ = _register_login(email)
    resp = client.post(
        "/api/auth/associations", json={"name": name, "email": f"{name}@example.com"}
    )
    assert resp.status_code == 201, resp.text
    return client, resp.json()["id"]


def _member(session: Session, assoc_id: str, email: str, role: Role) -> TestClient:
    client, uid = _register_login(email)
    session.add(Membership(user_id=uid, association_id=assoc_id, role=role))
    session.commit()
    return client


def test_regime_off_by_default():
    admin, assoc = _admin_with_association("a@example.com", "alpha")
    ctx = admin.get(f"/api/asso/{assoc}").json()
    assert ctx["regime_tva"] is False


def test_admin_can_enable_regime():
    admin, assoc = _admin_with_association("a@example.com", "alpha")
    resp = admin.patch(f"/api/asso/{assoc}", json={"regime_tva": True})
    assert resp.status_code == 200, resp.text
    assert resp.json()["regime_tva"] is True
    assert admin.get(f"/api/asso/{assoc}").json()["regime_tva"] is True


def test_treasurer_cannot_change_settings(session: Session):
    _, assoc = _admin_with_association("a@example.com", "alpha")
    treso = _member(session, assoc, "t@example.com", Role.TREASURER)
    resp = treso.patch(f"/api/asso/{assoc}", json={"regime_tva": True})
    assert resp.status_code == 403


def test_non_member_cannot_change_settings(session: Session):
    _, assoc = _admin_with_association("a@example.com", "alpha")
    outsider, _ = _register_login("out@example.com")
    resp = outsider.patch(f"/api/asso/{assoc}", json={"regime_tva": True})
    assert resp.status_code == 404  # no membership: existence not leaked
