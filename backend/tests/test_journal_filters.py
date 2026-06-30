"""Rich journal filters (T4): by operation type, category, tiers and date range.

The journal already filters by treasury account (``compte_id``), journal, statut
and free text. This adds the type-first filters a treasurer reasons with —
Recette / Dépense / Virement (recette/dépense derived from the category's sens,
virement from the entry origine; a manual entry carries no category and so
matches none of the three) — plus category, tiers and a date range. Every filter
is applied on top of the mandatory ``association_id`` scope and composes with the
others (AND), never widening access.
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from database import get_session
from main import _fastapi_app as app

PASSWORD = "password123"


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


def _categorie_id(client: TestClient, assoc: str, libelle: str) -> str:
    cats = client.get(f"/api/asso/{assoc}/categories").json()
    return next(c["id"] for c in cats if c["libelle"] == libelle)


def _treso_id(client: TestClient, assoc: str, numero: str) -> str:
    comptes = client.get(f"/api/asso/{assoc}/tresorerie").json()
    return next(c["id"] for c in comptes if c["numero"] == numero)


def _compte_id(client: TestClient, assoc: str, numero: str) -> str:
    comptes = client.get(f"/api/asso/{assoc}/comptes", params={"search": numero}).json()
    return next(c["id"] for c in comptes if c["numero"] == numero)


def _create_tiers(client: TestClient, assoc: str, nom: str) -> str:
    resp = client.post(
        f"/api/asso/{assoc}/tiers", json={"nom": nom, "type": "donateur"}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _post_simple(
    client: TestClient,
    assoc: str,
    libelle: str,
    montant: str,
    jour: str,
    tiers_id: str | None = None,
) -> dict:
    body = {
        "categorie_id": _categorie_id(client, assoc, libelle),
        "compte_tresorerie_id": _treso_id(client, assoc, "512"),
        "montant": montant,
        "date": jour,
    }
    if tiers_id is not None:
        body["tiers_id"] = tiers_id
    resp = client.post(f"/api/asso/{assoc}/ecritures/simple", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _post_virement(client: TestClient, assoc: str, montant: str, jour: str) -> dict:
    resp = client.post(
        f"/api/asso/{assoc}/ecritures/virement",
        json={
            "compte_source_id": _treso_id(client, assoc, "531"),
            "compte_destination_id": _treso_id(client, assoc, "512"),
            "montant": montant,
            "date": jour,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _post_manuel(client: TestClient, assoc: str, montant: str, jour: str) -> dict:
    """A manual dépense-looking entry (D 613 / C 512), with no category."""
    resp = client.post(
        f"/api/asso/{assoc}/ecritures",
        json={
            "journal_id": next(
                j["id"]
                for j in client.get(f"/api/asso/{assoc}/journaux").json()
                if j["code"] == "OD"
            ),
            "date": jour,
            "libelle": "Écriture manuelle",
            "lignes": [
                {"compte_id": _compte_id(client, assoc, "613"), "debit": montant},
                {"compte_id": _treso_id(client, assoc, "512"), "credit": montant},
            ],
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _mixed_books() -> tuple[TestClient, str, dict]:
    """One recette, one dépense, one virement and one manual entry, dated apart."""
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    donateur = _create_tiers(admin, assoc, "M. Dupont")
    recette = _post_simple(
        admin, assoc, "Cotisations", "150.00", "2026-03-15", donateur
    )
    depense = _post_simple(admin, assoc, "Locations", "100.00", "2026-06-27")
    virement = _post_virement(admin, assoc, "50.00", "2026-09-01")
    manuel = _post_manuel(admin, assoc, "30.00", "2026-06-15")
    refs = {
        "recette": recette,
        "depense": depense,
        "virement": virement,
        "manuel": manuel,
        "donateur": donateur,
    }
    return admin, assoc, refs


def _ids(rows: list[dict]) -> set[str]:
    return {r["id"] for r in rows}


# --- Free-text search escaping -------------------------------------------


def test_escape_like_neutralizes_wildcards():
    """User free text is data, not a LIKE pattern: % and _ (and the escape char)
    must be escaped so a search for 'TVA 20%' or 'REF_001' is taken literally."""
    from accounting_filters import escape_like

    assert escape_like("20%") == "20\\%"
    assert escape_like("REF_001") == "REF\\_001"
    assert escape_like("a\\b") == "a\\\\b"
    assert escape_like("plain") == "plain"


# --- Type filter ----------------------------------------------------------


def test_filter_type_recette_returns_only_recettes():
    admin, assoc, refs = _mixed_books()
    rows = admin.get(
        f"/api/asso/{assoc}/ecritures", params={"type_operation": "recette"}
    ).json()
    assert _ids(rows) == {refs["recette"]["id"]}


def test_filter_type_depense_returns_only_depenses():
    admin, assoc, refs = _mixed_books()
    rows = admin.get(
        f"/api/asso/{assoc}/ecritures", params={"type_operation": "depense"}
    ).json()
    # The manual entry debits a charge account but carries no category -> excluded.
    assert _ids(rows) == {refs["depense"]["id"]}


def test_filter_type_virement_returns_only_virements():
    admin, assoc, refs = _mixed_books()
    rows = admin.get(
        f"/api/asso/{assoc}/ecritures", params={"type_operation": "virement"}
    ).json()
    assert _ids(rows) == {refs["virement"]["id"]}


def test_filter_type_rejects_unknown_value():
    admin, assoc, _ = _mixed_books()
    resp = admin.get(
        f"/api/asso/{assoc}/ecritures", params={"type_operation": "bitcoin"}
    )
    assert resp.status_code == 422


def test_filter_type_accepts_several_values_or():
    """Repeated ``type_operation`` is an OR within the facet (recette OR virement)."""
    admin, assoc, refs = _mixed_books()
    rows = admin.get(
        f"/api/asso/{assoc}/ecritures",
        params={"type_operation": ["recette", "virement"]},
    ).json()
    assert _ids(rows) == {refs["recette"]["id"], refs["virement"]["id"]}


# --- Category & tiers filters ---------------------------------------------


def test_filter_by_categorie():
    admin, assoc, refs = _mixed_books()
    cat = _categorie_id(admin, assoc, "Cotisations")
    rows = admin.get(
        f"/api/asso/{assoc}/ecritures", params={"categorie_id": cat}
    ).json()
    assert _ids(rows) == {refs["recette"]["id"]}


def test_filter_by_several_categories_or():
    admin, assoc, refs = _mixed_books()
    cats = [
        _categorie_id(admin, assoc, "Cotisations"),
        _categorie_id(admin, assoc, "Locations"),
    ]
    rows = admin.get(
        f"/api/asso/{assoc}/ecritures", params={"categorie_id": cats}
    ).json()
    assert _ids(rows) == {refs["recette"]["id"], refs["depense"]["id"]}


def test_filter_by_tiers():
    admin, assoc, refs = _mixed_books()
    rows = admin.get(
        f"/api/asso/{assoc}/ecritures", params={"tiers_id": refs["donateur"]}
    ).json()
    assert _ids(rows) == {refs["recette"]["id"]}


# --- Date range filter ----------------------------------------------------


def test_filter_by_date_range_inclusive():
    admin, assoc, refs = _mixed_books()
    rows = admin.get(
        f"/api/asso/{assoc}/ecritures",
        params={"date_from": "2026-06-01", "date_to": "2026-06-30"},
    ).json()
    # June entries: the dépense (27th) and the manual entry (15th).
    assert _ids(rows) == {refs["depense"]["id"], refs["manuel"]["id"]}


def test_filter_by_date_from_only():
    admin, assoc, refs = _mixed_books()
    rows = admin.get(
        f"/api/asso/{assoc}/ecritures", params={"date_from": "2026-08-01"}
    ).json()
    assert _ids(rows) == {refs["virement"]["id"]}


# --- Composition (AND) ----------------------------------------------------


def test_filters_compose_with_and():
    admin, assoc, refs = _mixed_books()
    # A recette, but constrained to a window that excludes it -> empty.
    rows = admin.get(
        f"/api/asso/{assoc}/ecritures",
        params={"type_operation": "recette", "date_to": "2026-01-31"},
    ).json()
    assert rows == []

    # Same recette, within its window -> found.
    rows = admin.get(
        f"/api/asso/{assoc}/ecritures",
        params={"type_operation": "recette", "date_from": "2026-03-01"},
    ).json()
    assert _ids(rows) == {refs["recette"]["id"]}


# --- Isolation ------------------------------------------------------------


def test_foreign_category_and_tiers_match_nothing():
    admin_a, assoc_a, _ = _mixed_books()
    admin_b, assoc_b = _admin_with_association("b@example.com", "beta")
    foreign_cat = _categorie_id(admin_b, assoc_b, "Cotisations")
    foreign_tiers = _create_tiers(admin_b, assoc_b, "Autre")

    # A foreign id never widens access: it simply matches none of A's entries.
    assert (
        admin_a.get(
            f"/api/asso/{assoc_a}/ecritures", params={"categorie_id": foreign_cat}
        ).json()
        == []
    )
    assert (
        admin_a.get(
            f"/api/asso/{assoc_a}/ecritures", params={"tiers_id": foreign_tiers}
        ).json()
        == []
    )


def test_filters_do_not_bypass_tenant_isolation():
    admin_a, assoc_a, _ = _mixed_books()
    admin_b, assoc_b = _admin_with_association("b@example.com", "beta")

    # A member of B cannot read A's journal, filtered or not.
    assert (
        admin_b.get(
            f"/api/asso/{assoc_a}/ecritures", params={"type_operation": "recette"}
        ).status_code
        == 404
    )
