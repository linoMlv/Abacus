"""Fiscal-year closing: result determination, report à nouveau, locking, scoping.

Closing an exercice books the result-determination entry (class 6/7 → 120/129),
opens the next year (created if absent), posts the report à nouveau carrying the
balance-sheet accounts forward with the chosen affectation, and locks the closed
year. Reported figures become exercice-scoped so the report à nouveau never
double-counts, and the determination stays out of income statements.
"""

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from database import get_session
from exports.data import bilan_data, compte_resultat_data
from main import _fastapi_app as app
from models import Membership, Role

PASSWORD = "password123"
YEAR = date.today().year


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


def _cat(client: TestClient, assoc: str, libelle: str) -> str:
    cats = client.get(f"/api/asso/{assoc}/categories").json()
    return next(c["id"] for c in cats if c["libelle"] == libelle)


def _treso(client: TestClient, assoc: str, numero: str) -> str:
    comptes = client.get(f"/api/asso/{assoc}/tresorerie").json()
    return next(c["id"] for c in comptes if c["numero"] == numero)


def _post(
    client: TestClient,
    assoc: str,
    libelle: str,
    montant: str,
    jour: str,
    validate: bool = True,
) -> dict:
    resp = client.post(
        f"/api/asso/{assoc}/ecritures/simple",
        json={
            "categorie_id": _cat(client, assoc, libelle),
            "compte_tresorerie_id": _treso(client, assoc, "512"),
            "montant": montant,
            "date": jour,
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    if validate:
        assert (
            client.post(
                f"/api/asso/{assoc}/ecritures/{data['id']}/validation"
            ).status_code
            == 200
        )
    return data


def _entries(client: TestClient, assoc: str) -> list[dict]:
    return client.get(f"/api/asso/{assoc}/ecritures", params={"limit": 200}).json()


def _lines_of(
    client: TestClient, assoc: str, ecriture_id: str
) -> set[tuple[str, str, str]]:
    detail = client.get(f"/api/asso/{assoc}/ecritures/{ecriture_id}").json()
    comptes = {
        c["id"]: c["numero"] for c in client.get(f"/api/asso/{assoc}/comptes").json()
    }
    return {
        (comptes[line["compte_id"]], line["debit"], line["credit"])
        for line in detail["lignes"]
    }


def _find(entries: list[dict], origine: str) -> dict:
    return next(e for e in entries if e["origine"] == origine)


def _close(
    client: TestClient, assoc: str, ex_id: str, report: str, reserves: str = "0"
):
    return client.post(
        f"/api/asso/{assoc}/exercices/{ex_id}/cloture",
        json={"report_a_nouveau": report, "reserves": reserves},
    )


def _books_excedent(email: str = "admin@example.com") -> tuple[TestClient, str, str]:
    """Recette 300 − dépense 100 = +200 excédent; returns (client, assoc, ex_id)."""
    client, assoc = _admin_with_association(email, "alpha")
    _post(client, assoc, "Cotisations", "300.00", f"{YEAR}-03-01")
    _post(client, assoc, "Fournitures administratives", "100.00", f"{YEAR}-04-01")
    ex_id = client.get(f"/api/asso/{assoc}/exercices").json()[0]["id"]
    return client, assoc, ex_id


# --- Happy path: excédent, full report à nouveau -------------------------


def test_closing_books_determination_report_and_opens_next_year():
    client, assoc, ex_id = _books_excedent()

    resp = _close(client, assoc, ex_id, "200.00")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["resultat"] == "200.00"
    assert body["exercice_cloture"]["statut"] == "cloture"
    suivant = body["exercice_suivant"]
    assert suivant["statut"] == "ouvert"
    assert suivant["date_debut"] == date(YEAR + 1, 1, 1).isoformat()
    assert suivant["date_fin"] == date(YEAR + 1, 12, 31).isoformat()

    exercices = client.get(f"/api/asso/{assoc}/exercices").json()
    assert len(exercices) == 2

    entries = _entries(client, assoc)
    determination = _find(entries, "cloture")
    assert determination["exercice_id"] == ex_id
    assert _lines_of(client, assoc, determination["id"]) == {
        ("756", "300.00", "0.00"),  # produit débité pour être soldé
        ("6064", "0.00", "100.00"),  # charge créditée pour être soldée
        ("120", "0.00", "200.00"),  # excédent au crédit du résultat
    }

    report = _find(entries, "a_nouveau")
    assert report["exercice_id"] == suivant["id"]
    assert _lines_of(client, assoc, report["id"]) == {
        ("512", "200.00", "0.00"),
        ("110", "0.00", "200.00"),
    }


def test_closing_keeps_treasury_solde_single_counted():
    client, assoc, ex_id = _books_excedent("t@example.com")
    _close(client, assoc, ex_id, "200.00")
    # Report à nouveau restates 512; the current solde must stay 200, not 400.
    comptes = client.get(f"/api/asso/{assoc}/tresorerie").json()
    assert next(c["solde"] for c in comptes if c["numero"] == "512") == "200.00"


def test_income_statement_excludes_the_determination_entry():
    client, assoc, ex_id = _books_excedent("q@example.com")
    _close(client, assoc, ex_id, "200.00")
    synth = client.get(
        f"/api/asso/{assoc}/synthese",
        params={"date_from": f"{YEAR}-01-01", "date_to": f"{YEAR}-12-31"},
    ).json()
    assert synth["resultat"]["resultat"] == "200.00"


# --- Affectation variants -------------------------------------------------


def test_closing_can_split_result_between_report_and_reserves():
    client, assoc, ex_id = _books_excedent("s@example.com")
    _close(client, assoc, ex_id, "150.00", "50.00")
    report = _find(_entries(client, assoc), "a_nouveau")
    assert _lines_of(client, assoc, report["id"]) == {
        ("512", "200.00", "0.00"),
        ("110", "0.00", "150.00"),
        ("106", "0.00", "50.00"),
    }


def test_closing_a_deficit_reports_to_119():
    client, assoc = _admin_with_association("d@example.com", "alpha")
    _post(client, assoc, "Cotisations", "100.00", f"{YEAR}-03-01")
    _post(client, assoc, "Fournitures administratives", "300.00", f"{YEAR}-04-01")
    ex_id = client.get(f"/api/asso/{assoc}/exercices").json()[0]["id"]

    resp = _close(client, assoc, ex_id, "200.00")
    assert resp.status_code == 200, resp.text
    assert resp.json()["resultat"] == "-200.00"
    report = _find(_entries(client, assoc), "a_nouveau")
    assert _lines_of(client, assoc, report["id"]) == {
        ("512", "0.00", "200.00"),
        ("119", "200.00", "0.00"),
    }


# --- Guards ----------------------------------------------------------------


def test_closing_rejects_a_wrong_affectation_total():
    client, assoc, ex_id = _books_excedent("w@example.com")
    assert _close(client, assoc, ex_id, "100.00").status_code == 400


def test_closing_is_refused_while_a_draft_remains():
    client, assoc = _admin_with_association("dr@example.com", "alpha")
    _post(client, assoc, "Cotisations", "300.00", f"{YEAR}-03-01", validate=False)
    ex_id = client.get(f"/api/asso/{assoc}/exercices").json()[0]["id"]
    assert _close(client, assoc, ex_id, "0").status_code == 409


def test_a_closed_exercice_cannot_be_closed_again():
    client, assoc, ex_id = _books_excedent("dc@example.com")
    assert _close(client, assoc, ex_id, "200.00").status_code == 200
    assert _close(client, assoc, ex_id, "200.00").status_code == 409


def test_a_closed_year_locks_further_entries():
    client, assoc, ex_id = _books_excedent("lk@example.com")
    _close(client, assoc, ex_id, "200.00")
    # No open exercice covers a date in the closed year anymore.
    resp = client.post(
        f"/api/asso/{assoc}/ecritures/simple",
        json={
            "categorie_id": _cat(client, assoc, "Cotisations"),
            "compte_tresorerie_id": _treso(client, assoc, "512"),
            "montant": "10.00",
            "date": f"{YEAR}-05-01",
        },
    )
    assert resp.status_code == 400, resp.text


def test_a_closed_year_entry_cannot_be_contrepasse():
    client, assoc, ex_id = _books_excedent("cp@example.com")
    recette = _find(_entries(client, assoc), "saisie_simple")
    _close(client, assoc, ex_id, "200.00")
    resp = client.post(f"/api/asso/{assoc}/ecritures/{recette['id']}/contrepassation")
    assert resp.status_code == 409, resp.text


def test_closing_requires_the_exercise_close_permission(session: Session):
    client, assoc, ex_id = _books_excedent("perm@example.com")
    treasurer = _client()
    uid = treasurer.post(
        "/api/auth/register",
        json={"email": "tr@example.com", "password": PASSWORD, "name": "T"},
    ).json()["id"]
    assert (
        treasurer.post(
            "/api/auth/login", json={"email": "tr@example.com", "password": PASSWORD}
        ).status_code
        == 200
    )
    session.add(Membership(user_id=uid, association_id=assoc, role=Role.TREASURER))
    session.commit()
    assert _close(treasurer, assoc, ex_id, "200.00").status_code == 403


def test_closing_is_tenant_isolated():
    _, assoc_a, ex_a = _books_excedent("ia@example.com")
    other, _ = _admin_with_association("ib@example.com", "beta")
    assert _close(other, assoc_a, ex_a, "200.00").status_code == 404


def test_bilan_and_income_statement_are_correct_after_closing(session: Session):
    client, assoc, ex_id = _books_excedent("bs@example.com")
    _close(client, assoc, ex_id, "200.00")

    # Closed year: the result sits in 120 among the class-1-5 balances, so the
    # sheet balances without re-adding it (displayed résultat is 0).
    closed = bilan_data(session, assoc, date(YEAR, 12, 31))
    assert closed.total_actif == closed.total_passif == Decimal("200.00")
    assert closed.resultat == Decimal("0.00")

    # Income statement of the closed year excludes the determination entry.
    cr = compte_resultat_data(session, assoc, date(YEAR, 1, 1), date(YEAR, 12, 31))
    assert cr.resultat == Decimal("200.00")

    # New year: the report à nouveau carries 512 forward (not double-counted).
    opened = bilan_data(session, assoc, date(YEAR + 1, 12, 31))
    assert opened.total_actif == opened.total_passif == Decimal("200.00")
