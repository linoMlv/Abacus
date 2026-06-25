"""Read endpoints for the accounting referential: scoping, filters, isolation."""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from accounting_seed import DEFAULT_JOURNALS, PLAN_COMPTABLE_ANC
from database import get_session
from main import _fastapi_app as app
from models import Membership, Role

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
    assert (
        client.post(
            "/api/auth/login", json={"email": email, "password": PASSWORD}
        ).status_code
        == 200
    )


def _admin_with_association(email: str, assoc_email: str) -> tuple[TestClient, str]:
    client = _client()
    _register(client, email)
    _login(client, email)
    resp = client.post(
        "/api/auth/associations",
        json={"name": assoc_email.split("@")[0], "email": assoc_email},
    )
    assert resp.status_code == 201, resp.text
    return client, resp.json()["id"]


def test_member_lists_referential():
    admin, assoc_id = _admin_with_association("admin@example.com", "a@example.com")

    comptes = admin.get(f"/api/asso/{assoc_id}/comptes")
    assert comptes.status_code == 200
    assert len(comptes.json()) == len(PLAN_COMPTABLE_ANC)
    # Sorted by account number.
    numeros = [c["numero"] for c in comptes.json()]
    assert numeros == sorted(numeros)

    journaux = admin.get(f"/api/asso/{assoc_id}/journaux").json()
    assert {j["code"] for j in journaux} == {c for c, _ in DEFAULT_JOURNALS}

    exercices = admin.get(f"/api/asso/{assoc_id}/exercices").json()
    assert len(exercices) == 1
    assert exercices[0]["statut"] == "ouvert"


def test_comptes_can_be_filtered_by_class_and_search():
    admin, assoc_id = _admin_with_association("admin@example.com", "a@example.com")

    classe7 = admin.get(f"/api/asso/{assoc_id}/comptes", params={"classe": 7}).json()
    assert classe7
    assert all(c["classe"] == 7 for c in classe7)
    assert any(c["numero"] == "756" for c in classe7)

    cotis = admin.get(
        f"/api/asso/{assoc_id}/comptes", params={"search": "Cotisation"}
    ).json()
    assert {c["numero"] for c in cotis} >= {"756", "6281"}


def test_viewer_can_read_referential(session: Session):
    admin, assoc_id = _admin_with_association("admin@example.com", "a@example.com")
    viewer = _client()
    viewer_id = _register(viewer, "viewer@example.com")
    _login(viewer, "viewer@example.com")
    session.add(
        Membership(user_id=viewer_id, association_id=assoc_id, role=Role.VIEWER)
    )
    session.commit()

    assert viewer.get(f"/api/asso/{assoc_id}/comptes").status_code == 200


def test_non_member_cannot_read_referential():
    admin_a, _ = _admin_with_association("a@example.com", "aa@example.com")
    _, assoc_b = _admin_with_association("b@example.com", "bb@example.com")

    # admin_a is not a member of B: 404 on every scoped referential route.
    assert admin_a.get(f"/api/asso/{assoc_b}/comptes").status_code == 404
    assert admin_a.get(f"/api/asso/{assoc_b}/journaux").status_code == 404
    assert admin_a.get(f"/api/asso/{assoc_b}/exercices").status_code == 404


def test_referential_requires_authentication():
    assert _client().get("/api/asso/whatever/comptes").status_code == 401
