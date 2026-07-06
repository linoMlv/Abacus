"""Fiscal-year budget (Phase 5): prévu per category vs réalisé from the ledger.

The budget is edited in the treasurer's own categories, one prévu amount per
fiscal year (upsert replaces the whole grid). Reading returns every active
category with its prévu, réalisé and écart plus per-sens totals and the
prévisionnel/réalisé results. Everything is gated by ``BUDGET_MANAGE`` and
tenant-scoped.
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
    client.post(
        "/api/auth/register",
        json={"email": email, "password": PASSWORD, "name": "User"},
    )
    client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
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


def _post_simple(
    client: TestClient, assoc: str, libelle: str, montant: str, validate: bool = True
) -> dict:
    resp = client.post(
        f"/api/asso/{assoc}/ecritures/simple",
        json={
            "categorie_id": _categorie_id(client, assoc, libelle),
            "compte_tresorerie_id": _treso_id(client, assoc, "512"),
            "montant": montant,
            "date": TODAY,
        },
    )
    assert resp.status_code == 201, resp.text
    entry = resp.json()
    if validate:
        assert (
            client.post(
                f"/api/asso/{assoc}/ecritures/{entry['id']}/validation"
            ).status_code
            == 200
        )
    return entry


def _put_budget(client: TestClient, assoc: str, prevu: dict[str, str]) -> dict:
    lignes = [
        {"categorie_id": _categorie_id(client, assoc, libelle), "montant_prevu": m}
        for libelle, m in prevu.items()
    ]
    ex = client.get(f"/api/asso/{assoc}/exercices").json()[0]["id"]
    resp = client.put(
        f"/api/asso/{assoc}/budget", json={"exercice_id": ex, "lignes": lignes}
    )
    return resp


def _ligne(budget: dict, libelle: str, cats: list[dict]) -> dict:
    cat_id = next(c["id"] for c in cats if c["libelle"] == libelle)
    return next(ligne for ligne in budget["lignes"] if ligne["categorie_id"] == cat_id)


# --- read ------------------------------------------------------------------


def test_get_budget_lists_all_active_categories_at_zero():
    admin, assoc = _admin_with_association("a@example.com", "alpha")
    cats = admin.get(f"/api/asso/{assoc}/categories").json()

    budget = admin.get(f"/api/asso/{assoc}/budget").json()

    assert len(budget["lignes"]) == len([c for c in cats if c["is_active"]])
    assert all(ligne["montant_prevu"] == "0.00" for ligne in budget["lignes"])
    assert all(ligne["realise"] == "0.00" for ligne in budget["lignes"])
    assert budget["resultat_prevu"] == "0.00"
    assert budget["resultat_realise"] == "0.00"


# --- upsert + réalisé ------------------------------------------------------


def test_put_then_get_reflects_prevu_realise_and_totals():
    admin, assoc = _admin_with_association("a@example.com", "alpha")
    assert (
        _put_budget(
            admin, assoc, {"Cotisations": "8000.00", "Locations": "1200.00"}
        ).status_code
        == 200
    )
    _post_simple(admin, assoc, "Cotisations", "6200.00")
    _post_simple(admin, assoc, "Locations", "1500.00")
    _post_simple(admin, assoc, "Cotisations", "999.00", validate=False)  # draft

    budget = admin.get(f"/api/asso/{assoc}/budget").json()
    cats = admin.get(f"/api/asso/{assoc}/categories").json()

    cot = _ligne(budget, "Cotisations", cats)
    assert cot["montant_prevu"] == "8000.00"
    assert cot["realise"] == "6200.00"  # the draft is excluded
    assert cot["ecart"] == "-1800.00"
    loc = _ligne(budget, "Locations", cats)
    assert loc["ecart"] == "300.00"  # over budget

    assert budget["total_recettes_prevu"] == "8000.00"
    assert budget["total_depenses_prevu"] == "1200.00"
    assert budget["resultat_prevu"] == "6800.00"
    assert budget["resultat_realise"] == "4700.00"


def test_upsert_replaces_grid_and_zero_removes_line():
    admin, assoc = _admin_with_association("a@example.com", "alpha")
    _put_budget(admin, assoc, {"Cotisations": "8000.00"})
    _put_budget(admin, assoc, {"Cotisations": "0.00", "Locations": "500.00"})

    budget = admin.get(f"/api/asso/{assoc}/budget").json()
    cats = admin.get(f"/api/asso/{assoc}/categories").json()
    assert _ligne(budget, "Cotisations", cats)["montant_prevu"] == "0.00"
    assert _ligne(budget, "Locations", cats)["montant_prevu"] == "500.00"


# --- RBAC ------------------------------------------------------------------


def test_budget_requires_budget_manage(session: Session):
    admin, assoc = _admin_with_association("a@example.com", "alpha")
    viewer = _member_client(session, assoc, "v@example.com", Role.VIEWER)
    assert viewer.get(f"/api/asso/{assoc}/budget").status_code == 403
    assert _put_budget(viewer, assoc, {"Cotisations": "10.00"}).status_code == 403
    # The treasurer holds BUDGET_MANAGE.
    treasurer = _member_client(session, assoc, "t@example.com", Role.TREASURER)
    assert treasurer.get(f"/api/asso/{assoc}/budget").status_code == 200


# --- validation & isolation ------------------------------------------------


def test_negative_prevu_rejected():
    admin, assoc = _admin_with_association("a@example.com", "alpha")
    ex = admin.get(f"/api/asso/{assoc}/exercices").json()[0]["id"]
    resp = admin.put(
        f"/api/asso/{assoc}/budget",
        json={
            "exercice_id": ex,
            "lignes": [
                {
                    "categorie_id": _categorie_id(admin, assoc, "Cotisations"),
                    "montant_prevu": "-5.00",
                }
            ],
        },
    )
    assert resp.status_code == 400


def test_foreign_categorie_and_exercice_rejected():
    admin_a, assoc_a = _admin_with_association("a@example.com", "alpha")
    admin_b, assoc_b = _admin_with_association("b@example.com", "beta")
    ex_a = admin_a.get(f"/api/asso/{assoc_a}/exercices").json()[0]["id"]
    ex_b = admin_b.get(f"/api/asso/{assoc_b}/exercices").json()[0]["id"]
    cat_b = _categorie_id(admin_b, assoc_b, "Cotisations")

    # A foreign category is unknown to A.
    assert (
        admin_a.put(
            f"/api/asso/{assoc_a}/budget",
            json={
                "exercice_id": ex_a,
                "lignes": [{"categorie_id": cat_b, "montant_prevu": "10.00"}],
            },
        ).status_code
        == 404
    )
    # A foreign exercice is unknown to A.
    assert (
        admin_a.put(
            f"/api/asso/{assoc_a}/budget",
            json={"exercice_id": ex_b, "lignes": []},
        ).status_code
        == 404
    )


def test_budget_is_tenant_scoped():
    admin_a, assoc_a = _admin_with_association("a@example.com", "alpha")
    admin_b, _ = _admin_with_association("b@example.com", "beta")
    # A member of B is a stranger to A: no existence leak.
    assert admin_b.get(f"/api/asso/{assoc_a}/budget").status_code == 404


def test_budget_export_requires_budget_manage(session: Session):
    admin, assoc = _admin_with_association("a@example.com", "alpha")
    viewer = _member_client(session, assoc, "v@example.com", Role.VIEWER)
    assert viewer.get(f"/api/asso/{assoc}/exports/budget.pdf").status_code == 403
    assert viewer.get(f"/api/asso/{assoc}/exports/budget.xlsx").status_code == 403
    # The admin can export.
    assert admin.get(f"/api/asso/{assoc}/exports/budget.pdf").status_code == 200
