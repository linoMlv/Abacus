"""Donation tax receipts: eligible dons, issuance, one-receipt-per-don, RBAC."""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from database import get_session
from main import _fastapi_app as app
from models import Membership, Role

PASSWORD = "password123"


@pytest.fixture(autouse=True)
def _use_test_session(session: Session):
    app.dependency_overrides[get_session] = lambda: session
    yield
    app.dependency_overrides.clear()


def _register_login(email: str) -> tuple[TestClient, str]:
    client = TestClient(app)
    reg = client.post(
        "/api/auth/register", json={"email": email, "password": PASSWORD, "name": "U"}
    )
    assert reg.status_code == 201, reg.text
    client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    return client, reg.json()["id"]


def _admin_with_association(email: str, name: str) -> tuple[TestClient, str]:
    client, _ = _register_login(email)
    resp = client.post(
        "/api/auth/associations", json={"name": name, "email": f"{name}@example.com"}
    )
    assert resp.status_code == 201, resp.text
    return client, resp.json()["id"]


def _fill_identity(admin, assoc):
    assert (
        admin.patch(
            f"/api/asso/{assoc}",
            json={
                "adresse": "1 rue des Lilas",
                "code_postal": "75001",
                "ville": "Paris",
                "rna": "W751234567",
            },
        ).status_code
        == 200
    )


def _donor(admin, assoc, nom="M. Dupont", with_address=True):
    body = {"nom": nom, "type": "donateur"}
    if with_address:
        body |= {"adresse": "3 rue Neuve", "code_postal": "69000", "ville": "Lyon"}
    resp = admin.post(f"/api/asso/{assoc}/tiers", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _don_category(admin, assoc):
    cats = admin.get(f"/api/asso/{assoc}/categories").json()
    return next(c for c in cats if c["libelle"] == "Dons manuels")["id"]


def _banque(admin, assoc):
    comptes = admin.get(f"/api/asso/{assoc}/tresorerie").json()
    return next(c for c in comptes if c["numero"] == "512")["id"]


def _post_don(admin, assoc, tiers_id, montant, date="2026-03-01"):
    resp = admin.post(
        f"/api/asso/{assoc}/ecritures/simple",
        json={
            "categorie_id": _don_category(admin, assoc),
            "compte_tresorerie_id": _banque(admin, assoc),
            "montant": montant,
            "date": date,
            "tiers_id": tiers_id,
        },
    )
    assert resp.status_code == 201, resp.text
    eid = resp.json()["id"]
    assert (
        admin.post(f"/api/asso/{assoc}/ecritures/{eid}/validation").status_code == 200
    )
    return eid


def test_lists_validated_dons_with_donor():
    admin, assoc = _admin_with_association("a@example.com", "alpha")
    donor = _donor(admin, assoc)
    eid = _post_don(admin, assoc, donor["id"], "500.00")

    dons = admin.get(f"/api/asso/{assoc}/dons").json()
    assert len(dons) == 1
    assert dons[0]["ecriture_id"] == eid
    assert dons[0]["montant"] == "500.00"
    assert dons[0]["recu_id"] is None


def test_draft_don_is_not_eligible():
    admin, assoc = _admin_with_association("a@example.com", "alpha")
    donor = _donor(admin, assoc)
    # Posted but NOT validated → not an official don yet.
    admin.post(
        f"/api/asso/{assoc}/ecritures/simple",
        json={
            "categorie_id": _don_category(admin, assoc),
            "compte_tresorerie_id": _banque(admin, assoc),
            "montant": "80.00",
            "date": "2026-03-01",
            "tiers_id": donor["id"],
        },
    )
    assert admin.get(f"/api/asso/{assoc}/dons").json() == []


def test_issue_receipt_for_single_don():
    admin, assoc = _admin_with_association("a@example.com", "alpha")
    _fill_identity(admin, assoc)
    donor = _donor(admin, assoc)
    eid = _post_don(admin, assoc, donor["id"], "500.00")

    resp = admin.post(
        f"/api/asso/{assoc}/recus",
        json={
            "tiers_id": donor["id"],
            "ecriture_ids": [eid],
            "date": "2026-04-01",
            "annee": 2026,
            "forme": "numeraire",
        },
    )
    assert resp.status_code == 201, resp.text
    recu = resp.json()
    assert recu["numero"] == 1
    assert recu["montant"] == "500.00"
    assert recu["tiers_nom"] == "M. Dupont"

    # The don now shows as receipted, and is no longer offered as un-receipted.
    dons = admin.get(f"/api/asso/{assoc}/dons").json()
    assert dons[0]["recu_id"] == recu["id"]
    assert admin.get(f"/api/asso/{assoc}/dons", params={"non_recu": True}).json() == []


def test_annual_cumulative_receipt_sums_dons():
    admin, assoc = _admin_with_association("a@example.com", "alpha")
    _fill_identity(admin, assoc)
    donor = _donor(admin, assoc)
    e1 = _post_don(admin, assoc, donor["id"], "120.00", "2026-02-01")
    e2 = _post_don(admin, assoc, donor["id"], "80.00", "2026-06-01")

    resp = admin.post(
        f"/api/asso/{assoc}/recus",
        json={
            "tiers_id": donor["id"],
            "ecriture_ids": [e1, e2],
            "date": "2026-12-31",
            "annee": 2026,
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["montant"] == "200.00"


def test_don_cannot_be_receipted_twice():
    admin, assoc = _admin_with_association("a@example.com", "alpha")
    _fill_identity(admin, assoc)
    donor = _donor(admin, assoc)
    eid = _post_don(admin, assoc, donor["id"], "500.00")
    body = {
        "tiers_id": donor["id"],
        "ecriture_ids": [eid],
        "date": "2026-04-01",
        "annee": 2026,
    }
    assert admin.post(f"/api/asso/{assoc}/recus", json=body).status_code == 201
    # A second receipt on the same don is refused.
    assert admin.post(f"/api/asso/{assoc}/recus", json=body).status_code == 400


def test_requires_association_fiscal_identity():
    admin, assoc = _admin_with_association("a@example.com", "alpha")
    donor = _donor(admin, assoc)  # identity NOT filled
    eid = _post_don(admin, assoc, donor["id"], "500.00")
    resp = admin.post(
        f"/api/asso/{assoc}/recus",
        json={
            "tiers_id": donor["id"],
            "ecriture_ids": [eid],
            "date": "2026-04-01",
            "annee": 2026,
        },
    )
    assert resp.status_code == 400
    assert "identité fiscale" in resp.json()["detail"].lower()


def test_requires_donor_address():
    admin, assoc = _admin_with_association("a@example.com", "alpha")
    _fill_identity(admin, assoc)
    donor = _donor(admin, assoc, with_address=False)
    eid = _post_don(admin, assoc, donor["id"], "500.00")
    resp = admin.post(
        f"/api/asso/{assoc}/recus",
        json={
            "tiers_id": donor["id"],
            "ecriture_ids": [eid],
            "date": "2026-04-01",
            "annee": 2026,
        },
    )
    assert resp.status_code == 400
    assert "donateur" in resp.json()["detail"].lower()


def test_delete_receipt_frees_the_don():
    admin, assoc = _admin_with_association("a@example.com", "alpha")
    _fill_identity(admin, assoc)
    donor = _donor(admin, assoc)
    eid = _post_don(admin, assoc, donor["id"], "500.00")
    recu = admin.post(
        f"/api/asso/{assoc}/recus",
        json={
            "tiers_id": donor["id"],
            "ecriture_ids": [eid],
            "date": "2026-04-01",
            "annee": 2026,
        },
    ).json()

    assert admin.delete(f"/api/asso/{assoc}/recus/{recu['id']}").status_code == 204
    # The don is offered again.
    assert (
        len(admin.get(f"/api/asso/{assoc}/dons", params={"non_recu": True}).json()) == 1
    )


def test_viewer_cannot_issue_receipt(session: Session):
    admin, assoc = _admin_with_association("a@example.com", "alpha")
    _fill_identity(admin, assoc)
    donor = _donor(admin, assoc)
    eid = _post_don(admin, assoc, donor["id"], "500.00")
    viewer, uid = _register_login("v@example.com")
    session.add(Membership(user_id=uid, association_id=assoc, role=Role.VIEWER))
    session.commit()
    resp = viewer.post(
        f"/api/asso/{assoc}/recus",
        json={
            "tiers_id": donor["id"],
            "ecriture_ids": [eid],
            "date": "2026-04-01",
            "annee": 2026,
        },
    )
    assert resp.status_code == 403


def test_receipt_isolation_cross_tenant():
    admin_a, assoc_a = _admin_with_association("a@example.com", "alpha")
    admin_b, assoc_b = _admin_with_association("b@example.com", "beta")
    _fill_identity(admin_a, assoc_a)
    donor_a = _donor(admin_a, assoc_a)
    don_a = _post_don(admin_a, assoc_a, donor_a["id"], "500.00")
    # B tries to receipt A's don/donor: not eligible in B's scope.
    _fill_identity(admin_b, assoc_b)
    resp = admin_b.post(
        f"/api/asso/{assoc_b}/recus",
        json={
            "tiers_id": donor_a["id"],
            "ecriture_ids": [don_a],
            "date": "2026-04-01",
            "annee": 2026,
        },
    )
    assert resp.status_code == 404  # donor not in B
