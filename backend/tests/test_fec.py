"""FEC export (Fichier des Écritures Comptables, arrêté du 29 juillet 2013).

One tab-separated row per accounting line, validated entries only, for a fiscal
year. Guarded by REPORT_EXPORT_FEC (stricter than the other exports).
"""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from database import get_session
from exports.fec import FEC_HEADER
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


def _cat(client, assoc, libelle):
    cats = client.get(f"/api/asso/{assoc}/categories").json()
    return next(c["id"] for c in cats if c["libelle"] == libelle)


def _treso(client, assoc, numero):
    comptes = client.get(f"/api/asso/{assoc}/tresorerie").json()
    return next(c["id"] for c in comptes if c["numero"] == numero)


def _post(client, assoc, libelle, montant, jour, validate=True):
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
        client.post(f"/api/asso/{assoc}/ecritures/{data['id']}/validation")
    return data


def _exercice_id(client, assoc):
    return client.get(f"/api/asso/{assoc}/exercices").json()[0]["id"]


def _rows(text: str) -> list[list[str]]:
    lines = text.splitlines()
    return [line.split("\t") for line in lines if line]


def test_fec_has_the_18_named_columns_and_one_row_per_line():
    client, assoc = _admin_with_association("admin@example.com", "alpha")
    _post(client, assoc, "Cotisations", "300.00", f"{YEAR}-03-01")

    resp = client.get(
        f"/api/asso/{assoc}/exports/fec",
        params={"exercice_id": _exercice_id(client, assoc)},
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/plain")
    assert "attachment" in resp.headers["content-disposition"]

    rows = _rows(resp.text)
    assert rows[0] == FEC_HEADER
    assert len(FEC_HEADER) == 18
    # The single balanced entry produced two lines (512 debit, 756 credit).
    assert len(rows) == 3  # header + two lines
    assert all(len(r) == 18 for r in rows)


def test_fec_maps_fields_and_formats_amounts():
    client, assoc = _admin_with_association("a@example.com", "alpha")
    _post(client, assoc, "Cotisations", "300.00", f"{YEAR}-03-01")

    rows = _rows(
        client.get(
            f"/api/asso/{assoc}/exports/fec",
            params={"exercice_id": _exercice_id(client, assoc)},
        ).text
    )
    header = rows[0]
    produit = next(r for r in rows[1:] if r[header.index("CompteNum")] == "756")
    assert produit[header.index("JournalCode")] == "VE"
    assert produit[header.index("CompteLib")] == "Cotisations"
    assert produit[header.index("EcritureDate")] == f"{YEAR}0301"
    assert produit[header.index("Credit")] == "300,00"
    assert produit[header.index("Debit")] == "0,00"
    assert produit[header.index("ValidDate")] != ""


def test_fec_excludes_drafts():
    client, assoc = _admin_with_association("d@example.com", "alpha")
    _post(client, assoc, "Cotisations", "300.00", f"{YEAR}-03-01", validate=False)
    rows = _rows(
        client.get(
            f"/api/asso/{assoc}/exports/fec",
            params={"exercice_id": _exercice_id(client, assoc)},
        ).text
    )
    assert len(rows) == 1  # header only


def test_fec_requires_the_export_permission(session: Session):
    client, assoc = _admin_with_association("perm@example.com", "alpha")
    treasurer = _client()
    uid = treasurer.post(
        "/api/auth/register",
        json={"email": "tr@example.com", "password": PASSWORD, "name": "T"},
    ).json()["id"]
    treasurer.post(
        "/api/auth/login", json={"email": "tr@example.com", "password": PASSWORD}
    )
    session.add(Membership(user_id=uid, association_id=assoc, role=Role.TREASURER))
    session.commit()
    resp = treasurer.get(
        f"/api/asso/{assoc}/exports/fec",
        params={"exercice_id": _exercice_id(client, assoc)},
    )
    assert resp.status_code == 403


def test_fec_is_tenant_isolated():
    client_a, assoc_a = _admin_with_association("ia@example.com", "alpha")
    other, _ = _admin_with_association("ib@example.com", "beta")
    resp = other.get(
        f"/api/asso/{assoc_a}/exports/fec",
        params={"exercice_id": _exercice_id(client_a, assoc_a)},
    )
    assert resp.status_code == 404
