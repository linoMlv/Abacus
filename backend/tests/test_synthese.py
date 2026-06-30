"""Dashboard synthesis (T6): period analytics + alerts in one tenant-scoped read.

``GET /api/asso/{id}/synthese?date_from&date_to`` consolidates, for the period:
the result (produits cl.7 − charges cl.6), the breakdown by category and by event,
the treasury balance curve (opening balance + cumulative daily movements), and the
current alerts (drafts to validate, events over budget, fiscal years past due).
Reading is open to any member; every query is scoped to the active association.
"""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from database import get_session
from main import _fastapi_app as app
from models import Exercice, ExerciceStatut

PASSWORD = "password123"
FROM = "2026-06-01"
TO = "2026-06-30"


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


def _set_solde_initial(client: TestClient, assoc: str, montant: str, jour: str) -> None:
    resp = client.post(
        f"/api/asso/{assoc}/tresorerie/{_treso_id(client, assoc, '512')}/solde-initial",
        json={"montant": montant, "date_solde_initial": jour},
    )
    assert resp.status_code == 200, resp.text


def _post_simple(
    client: TestClient,
    assoc: str,
    libelle: str,
    montant: str,
    jour: str,
    evenement_id: str | None = None,
    validate: bool = True,
) -> dict:
    body = {
        "categorie_id": _categorie_id(client, assoc, libelle),
        "compte_tresorerie_id": _treso_id(client, assoc, "512"),
        "montant": montant,
        "date": jour,
    }
    if evenement_id is not None:
        body["evenement_id"] = evenement_id
    resp = client.post(f"/api/asso/{assoc}/ecritures/simple", json=body)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    # Figures only count validated entries; validate by default so the books are
    # official. Tests of the drafts alert opt out with ``validate=False``.
    if validate:
        assert (
            client.post(
                f"/api/asso/{assoc}/ecritures/{data['id']}/validation"
            ).status_code
            == 200
        )
    return data


def _create_evenement(client: TestClient, assoc: str, nom: str, budget_dep: str) -> str:
    resp = client.post(
        f"/api/asso/{assoc}/evenements",
        json={"nom": nom, "budget_depenses": budget_dep, "couleur": "#7C3AED"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _books() -> tuple[TestClient, str, dict]:
    """An association with an opening balance and recettes/dépenses across the range.

    Opening (before the range): Banque +1000 on 2026-01-01 (à-nouveau).
    In range: +200 Cotisations & +100 Dons (2026-06-10), −50 Locations tagged
    "Gala" (2026-06-20, budget dépenses 10 → over budget). Out of range: +999 in
    July (must be ignored by the period analytics).
    """
    client, assoc = _admin_with_association("admin@example.com", "alpha")
    _set_solde_initial(client, assoc, "1000.00", "2026-01-01")
    gala = _create_evenement(client, assoc, "Gala", "10.00")
    _post_simple(client, assoc, "Cotisations", "200.00", "2026-06-10")
    _post_simple(client, assoc, "Dons manuels", "100.00", "2026-06-10")
    _post_simple(client, assoc, "Locations", "50.00", "2026-06-20", evenement_id=gala)
    _post_simple(client, assoc, "Cotisations", "999.00", "2026-07-05")
    return client, assoc, {"gala": gala}


def _synthese(client: TestClient, assoc: str, **params) -> dict:
    resp = client.get(f"/api/asso/{assoc}/synthese", params=params)
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_resultat_over_the_range():
    client, assoc, _ = _books()
    data = _synthese(client, assoc, date_from=FROM, date_to=TO)

    assert data["date_from"] == FROM
    assert data["date_to"] == TO
    # Produits = 200 + 100 (the July 999 is out of range); charges = 50.
    assert data["resultat"]["recettes"] == "300.00"
    assert data["resultat"]["depenses"] == "50.00"
    assert data["resultat"]["resultat"] == "250.00"


def test_repartition_categories():
    client, assoc, _ = _books()
    data = _synthese(client, assoc, date_from=FROM, date_to=TO)

    by_libelle = {c["libelle"]: c for c in data["repartition_categories"]}
    assert by_libelle["Cotisations"]["montant"] == "200.00"
    assert by_libelle["Cotisations"]["sens"] == "recette"
    assert by_libelle["Dons manuels"]["montant"] == "100.00"
    assert by_libelle["Locations"]["montant"] == "50.00"
    assert by_libelle["Locations"]["sens"] == "depense"


def test_repartition_evenements_over_the_range():
    client, assoc, _ = _books()
    data = _synthese(client, assoc, date_from=FROM, date_to=TO)

    events = {e["nom"]: e for e in data["repartition_evenements"]}
    assert events["Gala"]["depenses"] == "50.00"
    assert events["Gala"]["recettes"] == "0.00"
    assert events["Gala"]["resultat"] == "-50.00"


def test_courbe_tresorerie_opening_then_cumulative():
    client, assoc, _ = _books()
    data = _synthese(client, assoc, date_from=FROM, date_to=TO)

    points = [(p["date"], p["solde"]) for p in data["courbe_tresorerie"]]
    # Anchor at the start with the opening balance, then cumulative per movement day.
    assert points == [
        ("2026-06-01", "1000.00"),  # opening (à-nouveau on 2026-01-01)
        ("2026-06-10", "1300.00"),  # +200 +100
        ("2026-06-20", "1250.00"),  # −50
    ]


def test_alerte_brouillons_counts_unvalidated_entries():
    client, assoc, _ = _books()  # all validated (opening + the four entries)
    # The alert counts entries left as drafts (pending validation).
    _post_simple(client, assoc, "Cotisations", "10.00", "2026-06-15", validate=False)
    data = _synthese(client, assoc, date_from=FROM, date_to=TO)
    assert data["alertes"]["brouillons"] == 1


def test_alerte_evenement_depasse_budget():
    client, assoc, refs = _books()
    data = _synthese(client, assoc, date_from=FROM, date_to=TO)

    depasses = data["alertes"]["evenements_depasses"]
    assert [e["evenement_id"] for e in depasses] == [refs["gala"]]
    assert depasses[0]["budget_depenses"] == "10.00"
    assert depasses[0]["realise_depenses"] == "50.00"


def test_alerte_exercice_a_cloturer(session: Session):
    client, assoc, _ = _books()
    # A past, still-open fiscal year is due for closing.
    session.add(
        Exercice(
            association_id=assoc,
            libelle="2025",
            date_debut=date(2025, 1, 1),
            date_fin=date(2025, 12, 31),
            statut=ExerciceStatut.OUVERT,
        )
    )
    session.commit()

    data = _synthese(client, assoc, date_from=FROM, date_to=TO)
    a_cloturer = data["alertes"]["exercices_a_cloturer"]
    assert [e["libelle"] for e in a_cloturer] == ["2025"]


def test_default_range_falls_back_to_the_open_exercice():
    client, assoc, _ = _books()
    data = _synthese(client, assoc)  # no date params
    # Seeded exercice covers the current calendar year (2026).
    assert data["date_from"] == "2026-01-01"
    assert data["date_to"] == "2026-12-31"
    # The whole year: produits 200 + 100 + 999, charges 50.
    assert data["resultat"]["recettes"] == "1299.00"
    assert data["resultat"]["depenses"] == "50.00"


def test_synthese_is_tenant_scoped():
    client_a, assoc_a, _ = _books()
    client_b, assoc_b = _admin_with_association("b@example.com", "beta")

    # B cannot read A's synthesis (not a member → 404, no existence leak).
    assert client_b.get(f"/api/asso/{assoc_a}/synthese").status_code == 404
    # B's own synthesis is empty, never showing A's data.
    data_b = _synthese(client_b, assoc_b)
    assert data_b["resultat"]["recettes"] == "0.00"
    assert data_b["repartition_categories"] == []
    assert data_b["courbe_tresorerie"] == []
