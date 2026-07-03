"""Recurring entries: CRUD, due-date generation (proposition/auto), idempotency,
end date, isolation and RBAC."""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from database import get_session
from main import _fastapi_app as app
from models import Membership, Role
from recurrence_engine import add_months

PASSWORD = "password123"
TODAY = date.today()


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
        "/api/auth/associations", json={"name": name, "email": f"{name}@example.com"}
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


def _treasury_id(client: TestClient, assoc: str, numero: str) -> str:
    rows = client.get(f"/api/asso/{assoc}/tresorerie").json()
    return next(r["id"] for r in rows if r["numero"] == numero)


def _categorie_id(client: TestClient, assoc: str, libelle: str) -> str:
    cats = client.get(f"/api/asso/{assoc}/categories").json()
    return next(c["id"] for c in cats if c["libelle"] == libelle)


def _create(client: TestClient, assoc: str, **overrides) -> dict:
    body = {
        "libelle": "Loyer",
        "categorie_id": _categorie_id(client, assoc, "Cotisations"),
        "compte_tresorerie_id": _treasury_id(client, assoc, "512"),
        "montant": "100.00",
        "periodicite": "mensuelle",
        "prochaine_echeance": TODAY.isoformat(),
        "mode": "proposition",
    }
    body.update(overrides)
    resp = client.post(f"/api/asso/{assoc}/recurrences", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _generer(client: TestClient, assoc: str) -> int:
    resp = client.post(f"/api/asso/{assoc}/recurrences/generer")
    assert resp.status_code == 200, resp.text
    return resp.json()["generees"]


def _recurrence_entries(client: TestClient, assoc: str) -> list[dict]:
    return [
        e
        for e in client.get(f"/api/asso/{assoc}/ecritures").json()
        if e["origine"] == "recurrence"
    ]


# --- CRUD -----------------------------------------------------------------


def test_create_recurrence():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    rec = _create(admin, assoc)
    assert rec["libelle"] == "Loyer"
    assert rec["periodicite"] == "mensuelle"
    assert rec["mode"] == "proposition"
    assert rec["actif"] is True


def test_create_rejects_non_positive_amount():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    resp = admin.post(
        f"/api/asso/{assoc}/recurrences",
        json={
            "libelle": "X",
            "categorie_id": _categorie_id(admin, assoc, "Cotisations"),
            "compte_tresorerie_id": _treasury_id(admin, assoc, "512"),
            "montant": "0",
            "periodicite": "mensuelle",
            "prochaine_echeance": TODAY.isoformat(),
        },
    )
    assert resp.status_code == 400


def test_update_and_delete_recurrence():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    rec = _create(admin, assoc)

    patched = admin.patch(
        f"/api/asso/{assoc}/recurrences/{rec['id']}",
        json={"montant": "150.00", "actif": False},
    )
    assert patched.status_code == 200
    assert patched.json()["actif"] is False

    assert admin.delete(f"/api/asso/{assoc}/recurrences/{rec['id']}").status_code == 204
    assert admin.get(f"/api/asso/{assoc}/recurrences").json() == []


# --- Generation -----------------------------------------------------------


def test_generation_proposition_books_a_draft():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    rec = _create(admin, assoc, mode="proposition")

    assert _generer(admin, assoc) == 1
    entries = _recurrence_entries(admin, assoc)
    assert len(entries) == 1
    assert entries[0]["statut"] == "brouillon"
    assert entries[0]["recurrence_id"] == rec["id"]

    # The next due date advanced by one month (so it no longer falls due today).
    updated = admin.get(f"/api/asso/{assoc}/recurrences").json()[0]
    assert updated["prochaine_echeance"] == add_months(TODAY, 1).isoformat()


def test_generation_auto_books_a_validated_entry():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    _create(admin, assoc, mode="auto")

    assert _generer(admin, assoc) == 1
    entries = _recurrence_entries(admin, assoc)
    assert entries[0]["statut"] == "validee"


def test_generation_falls_back_to_category_label_when_libelle_cleared():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    rec = _create(admin, assoc)
    # Editing the libellé to empty must not produce label-less entries.
    admin.patch(f"/api/asso/{assoc}/recurrences/{rec['id']}", json={"libelle": ""})

    assert _generer(admin, assoc) == 1
    assert _recurrence_entries(admin, assoc)[0]["libelle"] == "Cotisations"


def test_end_date_can_be_cleared():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    rec = _create(admin, assoc, date_fin="2026-12-31")

    cleared = admin.patch(
        f"/api/asso/{assoc}/recurrences/{rec['id']}", json={"date_fin": None}
    )
    assert cleared.status_code == 200
    assert cleared.json()["date_fin"] is None


def test_generation_is_idempotent():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    _create(admin, assoc)
    assert _generer(admin, assoc) == 1
    # Running again the same day books nothing (échéance already advanced).
    assert _generer(admin, assoc) == 0
    assert len(_recurrence_entries(admin, assoc)) == 1


def test_end_date_deactivates_the_recurrence():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    _create(admin, assoc, date_fin=TODAY.isoformat())

    assert _generer(admin, assoc) == 1  # today's occurrence
    rec = admin.get(f"/api/asso/{assoc}/recurrences").json()[0]
    # Next échéance is past the end date → the recurrence is switched off.
    assert rec["actif"] is False


# --- Isolation & RBAC -----------------------------------------------------


def test_cross_tenant_recurrence_is_not_reachable():
    admin_a, assoc_a = _admin_with_association("a@example.com", "alpha")
    admin_b, assoc_b = _admin_with_association("b@example.com", "beta")
    rec_b = _create(admin_b, assoc_b)

    resp = admin_a.patch(
        f"/api/asso/{assoc_a}/recurrences/{rec_b['id']}", json={"actif": False}
    )
    assert resp.status_code == 404
    assert admin_a.get(f"/api/asso/{assoc_b}/recurrences").status_code == 404


def test_viewer_cannot_manage_recurrences(session: Session):
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    viewer = _member_client(session, assoc, "viewer@example.com", Role.VIEWER)
    assert viewer.get(f"/api/asso/{assoc}/recurrences").status_code == 403
    assert viewer.post(f"/api/asso/{assoc}/recurrences/generer").status_code == 403
