"""The journal export honors the active journal filters (item 8).

The quick journal export from the journal page reflects what the user is looking
at: the same faceted filter (statut, type, category…) is applied to the exported
document, via the shared ``journal_filter_clauses``.
"""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from accounting_filters import JournalFilter
from database import get_session
from exports.data import journal_data
from main import _fastapi_app as app
from models import EcritureStatut

PASSWORD = "password123"
TODAY = "2026-06-27"
PERIOD = (date(2026, 1, 1), date(2026, 12, 31))


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
        "/api/auth/associations",
        json={"name": name, "email": f"{name}@example.com"},
    )
    assert resp.status_code == 201, resp.text
    return client, resp.json()["id"]


def _categorie_id(client: TestClient, assoc_id: str) -> str:
    cats = client.get(f"/api/asso/{assoc_id}/categories").json()
    return next(c["id"] for c in cats if c["libelle"] == "Cotisations")


def _compte_id(client: TestClient, assoc_id: str, numero: str) -> str:
    comptes = client.get(
        f"/api/asso/{assoc_id}/comptes", params={"search": numero}
    ).json()
    return next(c["id"] for c in comptes if c["numero"] == numero)


def _make_simple(client: TestClient, assoc_id: str, montant: str) -> dict:
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
    return resp.json()


def test_journal_data_applies_the_statut_facet(session: Session):
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    draft = _make_simple(admin, assoc, "10.00")
    validated = _make_simple(admin, assoc, "20.00")
    assert (
        admin.post(
            f"/api/asso/{assoc}/ecritures/{validated['id']}/validation"
        ).status_code
        == 200
    )

    data = journal_data(
        session,
        assoc,
        JournalFilter(
            date_from=PERIOD[0],
            date_to=PERIOD[1],
            statut=[EcritureStatut.VALIDEE],
        ),
    )
    pieces = {ligne.numero_piece for ligne in data.lignes}
    assert validated["numero_piece"] in pieces
    assert draft["numero_piece"] not in pieces


def test_journal_export_endpoint_accepts_filters():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    _make_simple(admin, assoc, "10.00")

    resp = admin.get(
        f"/api/asso/{assoc}/exports/journal.pdf", params={"statut": "validee"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "application/pdf"


def test_journal_export_rejects_an_unknown_type():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")

    resp = admin.get(
        f"/api/asso/{assoc}/exports/journal.pdf",
        params={"type_operation": "bogus"},
    )
    assert resp.status_code == 422, resp.text
