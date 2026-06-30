"""Events (événements) — T5: an analytic axis tagging entries.

An ``Evenement`` groups the recettes and dépenses of an action/project (Gala
2026…), independently of the category. Its *réalisé* is computed from the tagged
entries — Σ produits (class 7) for recettes, Σ charges (class 6) for dépenses —
and compared to its optional budget. CRUD is gated by ``EVENT_MANAGE``
(trésorier+); reading is open to any member; every id is re-scoped to the active
association.
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


def _admin_with_association(email: str, name: str) -> tuple[TestClient, str]:
    client = _client()
    assert (
        client.post(
            "/api/auth/register",
            json={"email": email, "password": PASSWORD, "name": "User"},
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/api/auth/login", json={"email": email, "password": PASSWORD}
        ).status_code
        == 200
    )
    resp = client.post(
        "/api/auth/associations", json={"name": name, "email": f"{name}@example.com"}
    )
    assert resp.status_code == 201, resp.text
    return client, resp.json()["id"]


def _member_client(
    session: Session, association_id: str, email: str, role: Role
) -> TestClient:
    client = _client()
    user_id = client.post(
        "/api/auth/register",
        json={"email": email, "password": PASSWORD, "name": "M"},
    ).json()["id"]
    session.add(Membership(user_id=user_id, association_id=association_id, role=role))
    session.commit()
    client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    return client


def _categorie_id(client: TestClient, assoc: str, libelle: str) -> str:
    cats = client.get(f"/api/asso/{assoc}/categories").json()
    return next(c["id"] for c in cats if c["libelle"] == libelle)


def _treso_id(client: TestClient, assoc: str, numero: str) -> str:
    comptes = client.get(f"/api/asso/{assoc}/tresorerie").json()
    return next(c["id"] for c in comptes if c["numero"] == numero)


def _create_evenement(client: TestClient, assoc: str, nom: str, **extra) -> dict:
    resp = client.post(f"/api/asso/{assoc}/evenements", json={"nom": nom, **extra})
    assert resp.status_code == 201, resp.text
    return resp.json()


def _post_simple(
    client: TestClient, assoc: str, libelle: str, montant: str, evenement_id=None
) -> dict:
    body = {
        "categorie_id": _categorie_id(client, assoc, libelle),
        "compte_tresorerie_id": _treso_id(client, assoc, "512"),
        "montant": montant,
        "date": TODAY,
    }
    if evenement_id is not None:
        body["evenement_id"] = evenement_id
    resp = client.post(f"/api/asso/{assoc}/ecritures/simple", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


# --- CRUD -----------------------------------------------------------------


def test_create_and_list_evenement():
    admin, assoc = _admin_with_association("a@example.com", "alpha")
    created = _create_evenement(
        admin,
        assoc,
        "Gala 2026",
        budget_recettes="2000.00",
        budget_depenses="800.00",
        couleur="#7C3AED",
        date_debut="2026-09-01",
    )
    assert created["nom"] == "Gala 2026"
    assert created["statut"] == "actif"
    assert created["resultat"] == "0.00"

    listed = admin.get(f"/api/asso/{assoc}/evenements").json()
    assert [e["id"] for e in listed] == [created["id"]]


def test_create_requires_event_manage(session: Session):
    admin, assoc = _admin_with_association("a@example.com", "alpha")
    viewer = _member_client(session, assoc, "v@example.com", Role.VIEWER)
    resp = viewer.post(f"/api/asso/{assoc}/evenements", json={"nom": "X"})
    assert resp.status_code == 403
    # A viewer can still read the list.
    assert viewer.get(f"/api/asso/{assoc}/evenements").status_code == 200


def test_duplicate_name_rejected():
    admin, assoc = _admin_with_association("a@example.com", "alpha")
    _create_evenement(admin, assoc, "Gala")
    resp = admin.post(f"/api/asso/{assoc}/evenements", json={"nom": "Gala"})
    assert resp.status_code == 400


def test_update_evenement_budget_and_close():
    admin, assoc = _admin_with_association("a@example.com", "alpha")
    ev = _create_evenement(admin, assoc, "Gala")
    resp = admin.patch(
        f"/api/asso/{assoc}/evenements/{ev['id']}",
        json={"budget_recettes": "500.00", "statut": "cloture", "nom": "Gala 2026"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["budget_recettes"] == "500.00"
    assert body["statut"] == "cloture"
    assert body["nom"] == "Gala 2026"


# --- Réalisé (computed from tagged entries) -------------------------------


def test_realise_sums_produits_and_charges_of_tagged_entries():
    admin, assoc = _admin_with_association("a@example.com", "alpha")
    ev = _create_evenement(admin, assoc, "Gala", budget_recettes="200.00")
    # A recette (produit, class 7) and a dépense (charge, class 6) tagged on it.
    recette = _post_simple(admin, assoc, "Cotisations", "150.00", evenement_id=ev["id"])
    depense = _post_simple(admin, assoc, "Locations", "100.00", evenement_id=ev["id"])
    # An untagged recette must not count toward the event.
    _post_simple(admin, assoc, "Cotisations", "999.00")
    # Réalisé counts validated entries only.
    for entry in (recette, depense):
        admin.post(f"/api/asso/{assoc}/ecritures/{entry['id']}/validation")

    detail = admin.get(f"/api/asso/{assoc}/evenements/{ev['id']}").json()
    assert detail["realise_recettes"] == "150.00"
    assert detail["realise_depenses"] == "100.00"
    assert detail["resultat"] == "50.00"


def test_entry_records_its_evenement_and_journal_filters_by_it():
    admin, assoc = _admin_with_association("a@example.com", "alpha")
    ev = _create_evenement(admin, assoc, "Gala")
    tagged = _post_simple(admin, assoc, "Cotisations", "150.00", evenement_id=ev["id"])
    _post_simple(admin, assoc, "Locations", "100.00")  # untagged

    assert tagged["evenement_id"] == ev["id"]
    rows = admin.get(
        f"/api/asso/{assoc}/ecritures", params={"evenement_id": ev["id"]}
    ).json()
    assert {r["id"] for r in rows} == {tagged["id"]}


# --- Isolation ------------------------------------------------------------


def test_evenement_is_tenant_scoped():
    admin_a, assoc_a = _admin_with_association("a@example.com", "alpha")
    admin_b, assoc_b = _admin_with_association("b@example.com", "beta")
    ev_b = _create_evenement(admin_b, assoc_b, "Beta event")

    # A cannot read B's event, nor list/patch it.
    assert (
        admin_a.get(f"/api/asso/{assoc_a}/evenements/{ev_b['id']}").status_code == 404
    )
    # A member of B is a stranger to A.
    assert admin_b.get(f"/api/asso/{assoc_a}/evenements").status_code == 404


def test_tagging_with_a_foreign_evenement_is_rejected():
    admin_a, assoc_a = _admin_with_association("a@example.com", "alpha")
    admin_b, assoc_b = _admin_with_association("b@example.com", "beta")
    ev_b = _create_evenement(admin_b, assoc_b, "Beta event")

    resp = admin_a.post(
        f"/api/asso/{assoc_a}/ecritures/simple",
        json={
            "categorie_id": _categorie_id(admin_a, assoc_a, "Cotisations"),
            "compte_tresorerie_id": _treso_id(admin_a, assoc_a, "512"),
            "montant": "10.00",
            "date": TODAY,
            "evenement_id": ev_b["id"],
        },
    )
    assert resp.status_code == 400
