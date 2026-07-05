"""Third parties (tiers) mini-module (T3b).

A *tiers* is who an operation is with — a supplier, a member/client, a donor or
a funder. In this step it is an informative tag the treasurer can quick-add and
attach to an assisted entry (memorised on the entry, like the category). The
full third-party ledger (401/411 linkage, lettrage) comes later.
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


def _create_tiers(client: TestClient, assoc: str, nom: str, type_: str) -> dict:
    resp = client.post(f"/api/asso/{assoc}/tiers", json={"nom": nom, "type": type_})
    assert resp.status_code == 201, resp.text
    return resp.json()


def _cotisation_id(client: TestClient, assoc: str) -> str:
    return next(
        c["id"]
        for c in client.get(f"/api/asso/{assoc}/categories").json()
        if c["libelle"] == "Cotisations"
    )


def _banque_id(client: TestClient, assoc: str) -> str:
    return next(
        c["id"]
        for c in client.get(f"/api/asso/{assoc}/tresorerie").json()
        if c["numero"] == "512"
    )


# --- CRUD (quick-add + list) ----------------------------------------------


def test_create_and_list_tiers():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    created = _create_tiers(admin, assoc, "Mairie", "financeur")
    assert created["nom"] == "Mairie"
    assert created["type"] == "financeur"
    assert created["is_active"] is True

    listed = admin.get(f"/api/asso/{assoc}/tiers").json()
    assert [t["nom"] for t in listed] == ["Mairie"]


def test_list_filters_by_type():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    _create_tiers(admin, assoc, "Imprimeur", "fournisseur")
    _create_tiers(admin, assoc, "M. Don", "donateur")

    fournisseurs = admin.get(
        f"/api/asso/{assoc}/tiers", params={"type": "fournisseur"}
    ).json()
    assert [t["nom"] for t in fournisseurs] == ["Imprimeur"]


def test_tiers_name_is_unique_per_association():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    _create_tiers(admin, assoc, "Imprimeur", "fournisseur")
    resp = admin.post(
        f"/api/asso/{assoc}/tiers", json={"nom": "Imprimeur", "type": "fournisseur"}
    )
    assert resp.status_code == 400, resp.text


def test_create_tiers_rejects_unknown_type():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    resp = admin.post(
        f"/api/asso/{assoc}/tiers", json={"nom": "X", "type": "extraterrestre"}
    )
    assert resp.status_code == 422, resp.text


def test_create_tiers_rejects_blank_name():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    resp = admin.post(
        f"/api/asso/{assoc}/tiers", json={"nom": "   ", "type": "donateur"}
    )
    assert resp.status_code == 400, resp.text


# --- RBAC & isolation -----------------------------------------------------


def test_create_tiers_requires_manage_permission(session: Session):
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    viewer = _member_client(session, assoc, "v@example.com", Role.VIEWER)
    resp = viewer.post(
        f"/api/asso/{assoc}/tiers", json={"nom": "Mairie", "type": "financeur"}
    )
    assert resp.status_code == 403, resp.text


def test_tiers_are_isolated_per_tenant():
    admin_a, assoc_a = _admin_with_association("a@example.com", "alpha")
    admin_b, assoc_b = _admin_with_association("b@example.com", "beta")
    _create_tiers(admin_a, assoc_a, "Mairie A", "financeur")

    assert admin_b.get(f"/api/asso/{assoc_b}/tiers").json() == []


# --- Attaching a tiers to an assisted entry -------------------------------


def test_simple_entry_can_carry_a_tiers():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    tiers = _create_tiers(admin, assoc, "M. Dupont", "donateur")
    resp = admin.post(
        f"/api/asso/{assoc}/ecritures/simple",
        json={
            "categorie_id": _cotisation_id(admin, assoc),
            "compte_tresorerie_id": _banque_id(admin, assoc),
            "montant": "50.00",
            "date": TODAY,
            "tiers_id": tiers["id"],
        },
    )
    assert resp.status_code == 201, resp.text
    detail = admin.get(f"/api/asso/{assoc}/ecritures/{resp.json()['id']}").json()
    assert detail["tiers_id"] == tiers["id"]


def test_simple_entry_rejects_cross_tenant_tiers():
    admin_a, assoc_a = _admin_with_association("a@example.com", "alpha")
    admin_b, assoc_b = _admin_with_association("b@example.com", "beta")
    foreign = _create_tiers(admin_b, assoc_b, "Tiers B", "fournisseur")
    resp = admin_a.post(
        f"/api/asso/{assoc_a}/ecritures/simple",
        json={
            "categorie_id": _cotisation_id(admin_a, assoc_a),
            "compte_tresorerie_id": _banque_id(admin_a, assoc_a),
            "montant": "50.00",
            "date": TODAY,
            "tiers_id": foreign["id"],
        },
    )
    assert resp.status_code == 400, resp.text


# --- Address & edition (for donor receipts, §8) ---------------------------


def test_create_tiers_with_address():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    resp = admin.post(
        f"/api/asso/{assoc}/tiers",
        json={
            "nom": "M. Dupont",
            "type": "donateur",
            "adresse": "3 rue Neuve",
            "code_postal": "69000",
            "ville": "Lyon",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["adresse"] == "3 rue Neuve" and body["ville"] == "Lyon"


def test_update_tiers_address():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    tiers = _create_tiers(admin, assoc, "M. Martin", "donateur")
    resp = admin.patch(
        f"/api/asso/{assoc}/tiers/{tiers['id']}",
        json={
            "adresse": "10 av. des Fleurs",
            "code_postal": "31000",
            "ville": "Toulouse",
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["adresse"] == "10 av. des Fleurs"


def test_update_tiers_requires_permission(session: Session):
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    tiers = _create_tiers(admin, assoc, "M. Martin", "donateur")
    viewer = _client()
    uid = _register(viewer, "v@example.com")
    _login(viewer, "v@example.com")
    session.add(Membership(user_id=uid, association_id=assoc, role=Role.VIEWER))
    session.commit()
    resp = viewer.patch(f"/api/asso/{assoc}/tiers/{tiers['id']}", json={"ville": "X"})
    assert resp.status_code == 403


def test_update_cross_tenant_tiers_is_404():
    admin_a, assoc_a = _admin_with_association("a@example.com", "alpha")
    admin_b, assoc_b = _admin_with_association("b@example.com", "beta")
    foreign = _create_tiers(admin_b, assoc_b, "Tiers B", "donateur")
    resp = admin_a.patch(
        f"/api/asso/{assoc_a}/tiers/{foreign['id']}", json={"ville": "X"}
    )
    assert resp.status_code == 404
