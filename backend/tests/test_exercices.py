"""Fiscal-year management: creation with parametric dates, overlap guard, RBAC.

Closing itself lives in ``test_cloture.py``; here we only cover the CRUD that
lets an association open a new (possibly shifted) exercice — the target of a
report à nouveau.
"""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from database import get_session
from main import _fastapi_app as app
from models import Membership, Role

PASSWORD = "password123"
NEXT_YEAR = date.today().year + 1


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


def _next_year_body() -> dict:
    return {
        "libelle": str(NEXT_YEAR),
        "date_debut": date(NEXT_YEAR, 1, 1).isoformat(),
        "date_fin": date(NEXT_YEAR, 12, 31).isoformat(),
    }


def test_admin_creates_a_new_exercice():
    admin, assoc = _admin_with_association("admin@example.com", "a@example.com")

    resp = admin.post(f"/api/asso/{assoc}/exercices", json=_next_year_body())
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["libelle"] == str(NEXT_YEAR)
    assert body["statut"] == "ouvert"
    assert body["report_a_nouveau_genere"] is False

    exercices = admin.get(f"/api/asso/{assoc}/exercices").json()
    assert len(exercices) == 2
    # Listed most-recent first.
    assert exercices[0]["libelle"] == str(NEXT_YEAR)


def test_create_supports_a_shifted_fiscal_year():
    admin, assoc = _admin_with_association("admin@example.com", "a@example.com")
    resp = admin.post(
        f"/api/asso/{assoc}/exercices",
        json={
            "libelle": f"{NEXT_YEAR}-{NEXT_YEAR + 1}",
            "date_debut": date(NEXT_YEAR, 9, 1).isoformat(),
            "date_fin": date(NEXT_YEAR + 1, 8, 31).isoformat(),
        },
    )
    assert resp.status_code == 201, resp.text


def test_create_rejects_an_overlapping_period():
    admin, assoc = _admin_with_association("admin@example.com", "a@example.com")
    # The seeded exercice already covers the current civil year.
    this_year = date.today().year
    resp = admin.post(
        f"/api/asso/{assoc}/exercices",
        json={
            "libelle": "chevauche",
            "date_debut": date(this_year, 6, 1).isoformat(),
            "date_fin": date(this_year + 1, 5, 31).isoformat(),
        },
    )
    assert resp.status_code == 400, resp.text


def test_create_rejects_end_not_after_start():
    admin, assoc = _admin_with_association("admin@example.com", "a@example.com")
    resp = admin.post(
        f"/api/asso/{assoc}/exercices",
        json={
            "libelle": "inversé",
            "date_debut": date(NEXT_YEAR, 12, 31).isoformat(),
            "date_fin": date(NEXT_YEAR, 1, 1).isoformat(),
        },
    )
    assert resp.status_code == 400, resp.text


def test_create_requires_exercise_close_permission(session: Session):
    admin, assoc = _admin_with_association("admin@example.com", "a@example.com")
    treasurer = _client()
    tid = _register(treasurer, "treso@example.com")
    _login(treasurer, "treso@example.com")
    session.add(Membership(user_id=tid, association_id=assoc, role=Role.TREASURER))
    session.commit()

    resp = treasurer.post(f"/api/asso/{assoc}/exercices", json=_next_year_body())
    assert resp.status_code == 403, resp.text


def test_create_is_tenant_isolated():
    admin_a, _ = _admin_with_association("a@example.com", "aa@example.com")
    _, assoc_b = _admin_with_association("b@example.com", "bb@example.com")
    resp = admin_a.post(f"/api/asso/{assoc_b}/exercices", json=_next_year_body())
    assert resp.status_code == 404, resp.text
