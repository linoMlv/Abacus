"""Bulk journal actions: validate or delete several drafts in one call.

Best-effort and per-id: each entry is re-scoped to the active association, then
validated/deleted when eligible; ineligible ones (foreign id, already validated,
validated-on-delete) are reported as ignored, never silently affecting another
tenant. Gated by ENTRY_VALIDATE / ENTRY_DELETE.
"""

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


def _admin_with_association(email: str, name: str) -> tuple[TestClient, str]:
    client = _client()
    _register(client, email)
    _login(client, email)
    resp = client.post(
        "/api/auth/associations",
        json={"name": name, "email": f"{name}@example.com"},
    )
    assert resp.status_code == 201, resp.text
    return client, resp.json()["id"]


def _member_client(
    session: Session, assoc_id: str, email: str, role: Role
) -> TestClient:
    client = _client()
    uid = _register(client, email)
    _login(client, email)
    session.add(Membership(user_id=uid, association_id=assoc_id, role=role))
    session.commit()
    return client


def _categorie_id(client: TestClient, assoc_id: str) -> str:
    cats = client.get(f"/api/asso/{assoc_id}/categories").json()
    return next(c["id"] for c in cats if c["libelle"] == "Cotisations")


def _compte_id(client: TestClient, assoc_id: str, numero: str) -> str:
    comptes = client.get(
        f"/api/asso/{assoc_id}/comptes", params={"search": numero}
    ).json()
    return next(c["id"] for c in comptes if c["numero"] == numero)


def _make_draft(client: TestClient, assoc_id: str, montant: str) -> str:
    resp = client.post(
        f"/api/asso/{assoc_id}/ecritures/simple",
        json={
            "categorie_id": _categorie_id(client, assoc_id),
            "compte_tresorerie_id": _compte_id(client, assoc_id, "512"),
            "montant": montant,
            "date": TODAY,
            "libelle": "Cotisation",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _validate(client: TestClient, assoc_id: str, entry_id: str) -> None:
    assert (
        client.post(f"/api/asso/{assoc_id}/ecritures/{entry_id}/validation").status_code
        == 200
    )


def test_bulk_validate_validates_every_draft():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    a, b = _make_draft(admin, assoc, "10.00"), _make_draft(admin, assoc, "20.00")

    resp = admin.post(
        f"/api/asso/{assoc}/ecritures/validation-groupee", json={"ids": [a, b]}
    )
    assert resp.status_code == 200, resp.text
    assert set(resp.json()["traitees"]) == {a, b}
    assert resp.json()["ignorees"] == []
    for eid in (a, b):
        assert admin.get(f"/api/asso/{assoc}/ecritures/{eid}").json()["statut"] == (
            "validee"
        )


def test_bulk_validate_reports_ineligible_and_foreign_ids():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    draft = _make_draft(admin, assoc, "10.00")
    already = _make_draft(admin, assoc, "20.00")
    _validate(admin, assoc, already)

    resp = admin.post(
        f"/api/asso/{assoc}/ecritures/validation-groupee",
        json={"ids": [draft, already, "ghost-id"]},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["traitees"] == [draft]
    ignored = {item["id"] for item in body["ignorees"]}
    assert ignored == {already, "ghost-id"}


def test_bulk_validate_does_not_touch_another_tenant(session: Session):
    admin_a, assoc_a = _admin_with_association("a@example.com", "alpha")
    foreign = _make_draft(admin_a, assoc_a, "10.00")
    admin_b, assoc_b = _admin_with_association("b@example.com", "beta")

    resp = admin_b.post(
        f"/api/asso/{assoc_b}/ecritures/validation-groupee", json={"ids": [foreign]}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["traitees"] == []
    # A's entry is untouched: still a draft.
    assert admin_a.get(f"/api/asso/{assoc_a}/ecritures/{foreign}").json()["statut"] == (
        "brouillon"
    )


def test_bulk_validate_requires_permission(session: Session):
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    draft = _make_draft(admin, assoc, "10.00")
    viewer = _member_client(session, assoc, "viewer@example.com", Role.VIEWER)

    resp = viewer.post(
        f"/api/asso/{assoc}/ecritures/validation-groupee", json={"ids": [draft]}
    )
    assert resp.status_code == 403, resp.text


def test_bulk_delete_removes_drafts_but_keeps_validated():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    draft = _make_draft(admin, assoc, "10.00")
    validated = _make_draft(admin, assoc, "20.00")
    _validate(admin, assoc, validated)

    resp = admin.post(
        f"/api/asso/{assoc}/ecritures/suppression-groupee",
        json={"ids": [draft, validated]},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["traitees"] == [draft]
    assert {item["id"] for item in body["ignorees"]} == {validated}
    assert admin.get(f"/api/asso/{assoc}/ecritures/{draft}").status_code == 404
    assert admin.get(f"/api/asso/{assoc}/ecritures/{validated}").status_code == 200


def test_bulk_delete_requires_permission(session: Session):
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    draft = _make_draft(admin, assoc, "10.00")
    viewer = _member_client(session, assoc, "viewer@example.com", Role.VIEWER)

    resp = viewer.post(
        f"/api/asso/{assoc}/ecritures/suppression-groupee", json={"ids": [draft]}
    )
    assert resp.status_code == 403, resp.text
