"""Optional VAT wiring on the assisted saisie endpoint.

Covers the server-side masking (a rate is ignored while the régime is off — the
client is never trusted to enable VAT), the TTC split into HT + VAT, the correct
déductible/collectée account per sens, and the category default rate.
"""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from database import get_session
from main import _fastapi_app as app
from models import Association

PASSWORD = "password123"
TODAY = "2026-06-27"


@pytest.fixture(autouse=True)
def _use_test_session(session: Session):
    app.dependency_overrides[get_session] = lambda: session
    yield
    app.dependency_overrides.clear()


def _admin_with_association(email: str, name: str) -> tuple[TestClient, str]:
    client = TestClient(app)
    assert (
        client.post(
            "/api/auth/register",
            json={"email": email, "password": PASSWORD, "name": "U"},
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


def _enable_tva(session: Session, assoc_id: str) -> None:
    assoc = session.get(Association, assoc_id)
    assoc.regime_tva = True
    session.add(assoc)
    session.commit()


def _categorie(client: TestClient, assoc_id: str, libelle: str) -> dict:
    cats = client.get(f"/api/asso/{assoc_id}/categories").json()
    return next(c for c in cats if c["libelle"] == libelle)


def _compte_id(client: TestClient, assoc_id: str, numero: str) -> str:
    comptes = client.get(
        f"/api/asso/{assoc_id}/comptes", params={"search": numero}
    ).json()
    return next(c["id"] for c in comptes if c["numero"] == numero)


def _dec(value) -> Decimal:
    return Decimal(str(value))


def _post_simple(client, assoc, cat_id, compte, montant, **extra):
    return client.post(
        f"/api/asso/{assoc}/ecritures/simple",
        json={
            "categorie_id": cat_id,
            "compte_tresorerie_id": compte,
            "montant": montant,
            "date": TODAY,
            **extra,
        },
    )


def test_rate_is_ignored_while_regime_off(session: Session):
    """Zero trust: a client-sent rate must not enable VAT while the régime is off."""
    admin, assoc = _admin_with_association("a@example.com", "alpha")
    cat = _categorie(admin, assoc, "Locations")
    banque = _compte_id(admin, assoc, "512")

    resp = _post_simple(admin, assoc, cat["id"], banque, "100.00", tva_taux="20")
    assert resp.status_code == 201, resp.text
    assert len(resp.json()["lignes"]) == 2  # no VAT line


def test_depense_with_override_rate_books_deductible(session: Session):
    admin, assoc = _admin_with_association("a@example.com", "alpha")
    _enable_tva(session, assoc)
    cat = _categorie(admin, assoc, "Locations")
    banque = _compte_id(admin, assoc, "512")
    tva_ded = _compte_id(admin, assoc, "44566")

    resp = _post_simple(admin, assoc, cat["id"], banque, "100.00", tva_taux="20")
    assert resp.status_code == 201, resp.text
    lignes = {
        (li["compte_id"], _dec(li["debit"]), _dec(li["credit"]))
        for li in resp.json()["lignes"]
    }
    assert lignes == {
        (cat["compte_id"], _dec("83.33"), _dec("0")),
        (tva_ded, _dec("16.67"), _dec("0")),
        (banque, _dec("0"), _dec("100.00")),
    }


def test_recette_with_rate_books_collectee(session: Session):
    admin, assoc = _admin_with_association("a@example.com", "alpha")
    _enable_tva(session, assoc)
    cat = _categorie(admin, assoc, "Prestations de services")
    banque = _compte_id(admin, assoc, "512")
    tva_col = _compte_id(admin, assoc, "44571")

    resp = _post_simple(admin, assoc, cat["id"], banque, "100.00", tva_taux="20")
    assert resp.status_code == 201, resp.text
    lignes = {
        (li["compte_id"], _dec(li["debit"]), _dec(li["credit"]))
        for li in resp.json()["lignes"]
    }
    assert lignes == {
        (banque, _dec("100.00"), _dec("0")),
        (cat["compte_id"], _dec("0"), _dec("83.33")),
        (tva_col, _dec("0"), _dec("16.67")),
    }


def test_category_default_rate_is_applied(session: Session):
    """With no override, the category's default rate drives the split."""
    admin, assoc = _admin_with_association("a@example.com", "alpha")
    _enable_tva(session, assoc)
    # Give the "Locations" category a default 20% rate.
    cat = _categorie(admin, assoc, "Locations")
    patched = admin.patch(
        f"/api/asso/{assoc}/categories/{cat['id']}", json={"tva_taux": "20"}
    )
    assert patched.status_code == 200, patched.text
    banque = _compte_id(admin, assoc, "512")

    resp = _post_simple(admin, assoc, cat["id"], banque, "100.00")
    assert resp.status_code == 201, resp.text
    assert len(resp.json()["lignes"]) == 3


def test_zero_rate_stays_two_lines(session: Session):
    admin, assoc = _admin_with_association("a@example.com", "alpha")
    _enable_tva(session, assoc)
    cat = _categorie(admin, assoc, "Locations")
    banque = _compte_id(admin, assoc, "512")

    resp = _post_simple(admin, assoc, cat["id"], banque, "100.00", tva_taux="0")
    assert resp.status_code == 201, resp.text
    assert len(resp.json()["lignes"]) == 2
