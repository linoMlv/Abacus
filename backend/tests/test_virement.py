"""Internal transfers and payment metadata (T3a).

A *virement interne* moves money between two treasury accounts of the same
association. It posts a single balanced OD entry (D destination / C source),
``origine = virement``, with no impact on the result. Recette/dépense and
transfers may also carry an informative payment method and external reference.
"""

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from accounting_engine import EntryError, build_ecriture_virement
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


def _treso_id(client: TestClient, assoc_id: str, numero: str) -> str:
    comptes = client.get(f"/api/asso/{assoc_id}/tresorerie").json()
    return next(c["id"] for c in comptes if c["numero"] == numero)


def _compte_id(client: TestClient, assoc_id: str, numero: str) -> str:
    comptes = client.get(
        f"/api/asso/{assoc_id}/comptes", params={"search": numero}
    ).json()
    return next(c["id"] for c in comptes if c["numero"] == numero)


def _solde(client: TestClient, assoc_id: str, numero: str) -> Decimal:
    comptes = client.get(f"/api/asso/{assoc_id}/tresorerie").json()
    return Decimal(next(c["solde"] for c in comptes if c["numero"] == numero))


def _virement_payload(client: TestClient, assoc_id: str, montant: str) -> dict:
    return {
        "compte_source_id": _treso_id(client, assoc_id, "531"),  # caisse
        "compte_destination_id": _treso_id(client, assoc_id, "512"),  # banque
        "montant": montant,
        "date": TODAY,
    }


# --- Pure engine ----------------------------------------------------------


def test_engine_virement_books_debit_destination_credit_source():
    ecriture = build_ecriture_virement(
        association_id="a",
        exercice_id="e",
        journal_id="od",
        compte_source_id="caisse",
        compte_destination_id="banque",
        montant="200.00",
        date_ecriture=date(2026, 6, 27),
        libelle="Remise en banque",
        numero_piece=1,
    )
    assert ecriture.origine.value == "virement"
    by_compte = {ligne.compte_id: ligne for ligne in ecriture.lignes}
    assert by_compte["banque"].debit == Decimal("200.00")
    assert by_compte["banque"].credit == Decimal("0")
    assert by_compte["caisse"].credit == Decimal("200.00")
    assert by_compte["caisse"].debit == Decimal("0")


def test_engine_virement_rejects_same_account():
    with pytest.raises(EntryError):
        build_ecriture_virement(
            association_id="a",
            exercice_id="e",
            journal_id="od",
            compte_source_id="x",
            compte_destination_id="x",
            montant="10.00",
            date_ecriture=date(2026, 6, 27),
            libelle="boucle",
            numero_piece=1,
        )


def test_engine_virement_rejects_zero_amount():
    with pytest.raises(EntryError):
        build_ecriture_virement(
            association_id="a",
            exercice_id="e",
            journal_id="od",
            compte_source_id="caisse",
            compte_destination_id="banque",
            montant="0",
            date_ecriture=date(2026, 6, 27),
            libelle="vide",
            numero_piece=1,
        )


# --- Endpoint: internal transfer ------------------------------------------


def test_virement_creates_balanced_od_entry():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")

    resp = admin.post(
        f"/api/asso/{assoc}/ecritures/virement",
        json={**_virement_payload(admin, assoc, "200.00"), "libelle": "Remise"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["origine"] == "virement"

    banque = _treso_id(admin, assoc, "512")
    caisse = _treso_id(admin, assoc, "531")
    lignes = {ligne["compte_id"]: ligne for ligne in body["lignes"]}
    assert lignes[banque]["debit"] == "200.00"
    assert lignes[caisse]["credit"] == "200.00"

    # Booked into the OD (opérations diverses) journal.
    row = next(
        e
        for e in admin.get(f"/api/asso/{assoc}/ecritures").json()
        if e["id"] == body["id"]
    )
    assert row["journal_code"] == "OD"


def test_virement_moves_the_balances():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    created = admin.post(
        f"/api/asso/{assoc}/ecritures/virement",
        json=_virement_payload(admin, assoc, "120.00"),
    ).json()
    # Only a validated entry moves the (official) treasury soldes.
    admin.post(f"/api/asso/{assoc}/ecritures/{created['id']}/validation")
    # Caisse loses, banque gains (relative to their à-nouveau-less zero starts).
    assert _solde(admin, assoc, "512") == Decimal("120.00")
    assert _solde(admin, assoc, "531") == Decimal("-120.00")


def test_virement_rejects_same_source_and_destination():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    banque = _treso_id(admin, assoc, "512")
    resp = admin.post(
        f"/api/asso/{assoc}/ecritures/virement",
        json={
            "compte_source_id": banque,
            "compte_destination_id": banque,
            "montant": "50.00",
            "date": TODAY,
        },
    )
    assert resp.status_code == 400, resp.text


def test_virement_rejects_non_treasury_account():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    charge = _compte_id(admin, assoc, "6064")  # a charge account, not treasury
    resp = admin.post(
        f"/api/asso/{assoc}/ecritures/virement",
        json={
            "compte_source_id": _treso_id(admin, assoc, "531"),
            "compte_destination_id": charge,
            "montant": "50.00",
            "date": TODAY,
        },
    )
    assert resp.status_code == 400, resp.text


def test_virement_rejects_cross_tenant_account():
    admin_a, assoc_a = _admin_with_association("a@example.com", "alpha")
    admin_b, assoc_b = _admin_with_association("b@example.com", "beta")
    foreign = _treso_id(admin_b, assoc_b, "512")
    resp = admin_a.post(
        f"/api/asso/{assoc_a}/ecritures/virement",
        json={
            "compte_source_id": _treso_id(admin_a, assoc_a, "531"),
            "compte_destination_id": foreign,
            "montant": "50.00",
            "date": TODAY,
        },
    )
    assert resp.status_code == 400, resp.text
    # And nothing leaked into B.
    assert admin_b.get(f"/api/asso/{assoc_b}/ecritures").json() == []


def test_virement_requires_create_permission(session: Session):
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    viewer = _member_client(session, assoc, "v@example.com", Role.VIEWER)
    resp = viewer.post(
        f"/api/asso/{assoc}/ecritures/virement",
        json=_virement_payload(admin, assoc, "10.00"),
    )
    assert resp.status_code == 403, resp.text


def test_virement_persists_payment_metadata():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    resp = admin.post(
        f"/api/asso/{assoc}/ecritures/virement",
        json={
            **_virement_payload(admin, assoc, "75.00"),
            "reference_externe": "VIR-2026-001",
            "mode_reglement": "virement",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["reference_externe"] == "VIR-2026-001"
    assert body["mode_reglement"] == "virement"
