"""Editing a draft entry (PATCH): rebuild in place, immutability and isolation.

A *brouillon* can be edited freely — its content is rebuilt through the same
per-origine builder as creation, keeping the voucher number. A *validated* entry
is immutable (409 — correction goes through contre-passation). Editing is gated
by the create permission of the entry's origine and tenant-scoped (A→B = 404).
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


def _categorie(client: TestClient, assoc_id: str, libelle: str) -> dict:
    cats = client.get(f"/api/asso/{assoc_id}/categories").json()
    return next(c for c in cats if c["libelle"] == libelle)


def _compte_id(client: TestClient, assoc_id: str, numero: str) -> str:
    comptes = client.get(
        f"/api/asso/{assoc_id}/comptes", params={"search": numero}
    ).json()
    return next(c["id"] for c in comptes if c["numero"] == numero)


def _simple_body(client: TestClient, assoc_id: str, libelle: str, montant: str) -> dict:
    return {
        "categorie_id": _categorie(client, assoc_id, "Cotisations")["id"],
        "compte_tresorerie_id": _compte_id(client, assoc_id, "512"),
        "montant": montant,
        "date": TODAY,
        "libelle": libelle,
    }


def _create_simple_draft(client: TestClient, assoc_id: str, montant: str) -> dict:
    resp = client.post(
        f"/api/asso/{assoc_id}/ecritures/simple",
        json=_simple_body(client, assoc_id, "Cotisation initiale", montant),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_edit_simple_draft_rebuilds_lines_keeping_voucher():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    draft = _create_simple_draft(admin, assoc, "150.00")

    resp = admin.patch(
        f"/api/asso/{assoc}/ecritures/{draft['id']}",
        json={"simple": _simple_body(admin, assoc, "Cotisation corrigée", "200.00")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["statut"] == "brouillon"
    assert body["numero_piece"] == draft["numero_piece"]  # voucher preserved
    assert body["libelle"] == "Cotisation corrigée"
    # The treasury (debit) line now carries the new amount.
    debits = [ligne["debit"] for ligne in body["lignes"]]
    assert "200.00" in debits
    assert "150.00" not in debits


def test_edit_validated_entry_is_409():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    draft = _create_simple_draft(admin, assoc, "150.00")
    assert (
        admin.post(f"/api/asso/{assoc}/ecritures/{draft['id']}/validation").status_code
        == 200
    )

    resp = admin.patch(
        f"/api/asso/{assoc}/ecritures/{draft['id']}",
        json={"simple": _simple_body(admin, assoc, "Trop tard", "200.00")},
    )
    assert resp.status_code == 409, resp.text


def test_edit_other_tenant_entry_is_404():
    admin_a, assoc_a = _admin_with_association("a@example.com", "alpha")
    draft = _create_simple_draft(admin_a, assoc_a, "150.00")
    admin_b, assoc_b = _admin_with_association("b@example.com", "beta")

    # B forges A's entry id under B's own (legitimate) scope: no such entry → 404.
    resp = admin_b.patch(
        f"/api/asso/{assoc_b}/ecritures/{draft['id']}",
        json={"simple": _simple_body(admin_b, assoc_b, "Pirate", "1.00")},
    )
    assert resp.status_code == 404, resp.text


def test_edit_requires_the_origine_create_permission(session: Session):
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    draft = _create_simple_draft(admin, assoc, "150.00")
    viewer = _member_client(session, assoc, "viewer@example.com", Role.VIEWER)

    resp = viewer.patch(
        f"/api/asso/{assoc}/ecritures/{draft['id']}",
        json={"simple": _simple_body(admin, assoc, "Lecture seule", "200.00")},
    )
    assert resp.status_code == 403, resp.text
