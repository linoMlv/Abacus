"""Accounting-entry endpoints: posting, lifecycle, RBAC and tenant isolation."""

from decimal import Decimal

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


def _categorie(client: TestClient, assoc_id: str, libelle: str) -> dict:
    cats = client.get(f"/api/asso/{assoc_id}/categories").json()
    return next(c for c in cats if c["libelle"] == libelle)


def _compte_id(client: TestClient, assoc_id: str, numero: str) -> str:
    comptes = client.get(
        f"/api/asso/{assoc_id}/comptes", params={"search": numero}
    ).json()
    return next(c["id"] for c in comptes if c["numero"] == numero)


def _journal_id(client: TestClient, assoc_id: str, code: str) -> str:
    journaux = client.get(f"/api/asso/{assoc_id}/journaux").json()
    return next(j["id"] for j in journaux if j["code"] == code)


def _dec(value) -> Decimal:
    return Decimal(str(value))


def _simple_payload(client: TestClient, assoc_id: str, libelle: str, montant: str):
    return {
        "categorie_id": _categorie(client, assoc_id, libelle)["id"],
        "compte_tresorerie_id": _compte_id(client, assoc_id, "512"),
        "montant": montant,
        "date": TODAY,
    }


# --- Assisted (simple) creation -------------------------------------------


def test_simple_recette_creates_balanced_draft():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    cat = _categorie(admin, assoc, "Cotisations")
    banque = _compte_id(admin, assoc, "512")

    resp = admin.post(
        f"/api/asso/{assoc}/ecritures/simple",
        json={
            "categorie_id": cat["id"],
            "compte_tresorerie_id": banque,
            "montant": "150.00",
            "date": TODAY,
            "libelle": "Cotisation Dupont",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["statut"] == "brouillon"
    assert body["origine"] == "saisie_simple"
    assert body["numero_piece"] == 1

    lignes = body["lignes"]
    assert len(lignes) == 2
    debit = next(line for line in lignes if _dec(line["debit"]) > 0)
    credit = next(line for line in lignes if _dec(line["credit"]) > 0)
    # Recette: bank is debited, the produit account (category) is credited.
    assert debit["compte_id"] == banque
    assert credit["compte_id"] == cat["compte_id"]
    assert _dec(debit["debit"]) == _dec(credit["credit"]) == Decimal("150.00")


def test_simple_depense_debits_charge_and_credits_cash():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    cat = _categorie(admin, assoc, "Locations")
    banque = _compte_id(admin, assoc, "512")

    resp = admin.post(
        f"/api/asso/{assoc}/ecritures/simple",
        json={
            "categorie_id": cat["id"],
            "compte_tresorerie_id": banque,
            "montant": "100.00",
            "date": TODAY,
        },
    )
    assert resp.status_code == 201, resp.text
    lignes = resp.json()["lignes"]
    debit = next(line for line in lignes if _dec(line["debit"]) > 0)
    credit = next(line for line in lignes if _dec(line["credit"]) > 0)
    assert debit["compte_id"] == cat["compte_id"]
    assert credit["compte_id"] == banque


def test_simple_rejects_non_treasury_counterpart():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    cat = _categorie(admin, assoc, "Cotisations")
    produit = _compte_id(admin, assoc, "756")  # classe 7, pas de trésorerie

    resp = admin.post(
        f"/api/asso/{assoc}/ecritures/simple",
        json={
            "categorie_id": cat["id"],
            "compte_tresorerie_id": produit,
            "montant": "10.00",
            "date": TODAY,
        },
    )
    assert resp.status_code == 400
    assert "trésorerie" in resp.json()["detail"]


def test_simple_rejects_non_positive_amount():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    resp = admin.post(
        f"/api/asso/{assoc}/ecritures/simple",
        json=_simple_payload(admin, assoc, "Cotisations", "0"),
    )
    assert resp.status_code == 400


def test_simple_rejects_date_without_open_exercice():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    payload = _simple_payload(admin, assoc, "Cotisations", "10.00")
    payload["date"] = "2019-01-01"
    resp = admin.post(f"/api/asso/{assoc}/ecritures/simple", json=payload)
    assert resp.status_code == 400
    assert "exercice" in resp.json()["detail"].lower()


# --- Manual creation ------------------------------------------------------


def test_manual_entry_balanced_is_created():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    banque = _compte_id(admin, assoc, "512")
    cotis = _compte_id(admin, assoc, "756")

    resp = admin.post(
        f"/api/asso/{assoc}/ecritures",
        json={
            "journal_id": _journal_id(admin, assoc, "OD"),
            "date": TODAY,
            "libelle": "Régularisation",
            "lignes": [
                {"compte_id": banque, "debit": "100.00", "credit": "0"},
                {"compte_id": cotis, "debit": "0", "credit": "100.00"},
            ],
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["origine"] == "manuelle"


def test_manual_entry_rejects_unbalanced():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    banque = _compte_id(admin, assoc, "512")
    cotis = _compte_id(admin, assoc, "756")

    resp = admin.post(
        f"/api/asso/{assoc}/ecritures",
        json={
            "journal_id": _journal_id(admin, assoc, "OD"),
            "date": TODAY,
            "libelle": "Déséquilibrée",
            "lignes": [
                {"compte_id": banque, "debit": "100.00"},
                {"compte_id": cotis, "credit": "90.00"},
            ],
        },
    )
    assert resp.status_code == 400
    assert "déséquilibrée" in resp.json()["detail"].lower()


# --- Lifecycle: validation & deletion -------------------------------------


def _create_draft(client: TestClient, assoc: str) -> str:
    resp = client.post(
        f"/api/asso/{assoc}/ecritures/simple",
        json=_simple_payload(client, assoc, "Cotisations", "50.00"),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def test_validation_locks_the_entry():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    entry = _create_draft(admin, assoc)

    validated = admin.post(f"/api/asso/{assoc}/ecritures/{entry}/validation")
    assert validated.status_code == 200, validated.text
    assert validated.json()["statut"] == "validee"
    assert validated.json()["validated_at"] is not None

    # A validated entry is immutable: no re-validation, no deletion.
    assert (
        admin.post(f"/api/asso/{assoc}/ecritures/{entry}/validation").status_code == 409
    )
    assert admin.delete(f"/api/asso/{assoc}/ecritures/{entry}").status_code == 409


def test_draft_can_be_deleted():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    entry = _create_draft(admin, assoc)
    assert admin.delete(f"/api/asso/{assoc}/ecritures/{entry}").status_code == 204
    assert admin.get(f"/api/asso/{assoc}/ecritures/{entry}").status_code == 404


# --- RBAC -----------------------------------------------------------------


def test_viewer_cannot_create_entries(session: Session):
    _, assoc = _admin_with_association("admin@example.com", "alpha")
    viewer = _member_client(session, assoc, "viewer@example.com", Role.VIEWER)
    resp = viewer.post(
        f"/api/asso/{assoc}/ecritures/simple",
        json=_simple_payload(viewer, assoc, "Cotisations", "10.00"),
    )
    assert resp.status_code == 403


def test_treasurer_can_create_simple_but_not_manual(session: Session):
    _, assoc = _admin_with_association("admin@example.com", "alpha")
    treasurer = _member_client(session, assoc, "tres@example.com", Role.TREASURER)

    simple = treasurer.post(
        f"/api/asso/{assoc}/ecritures/simple",
        json=_simple_payload(treasurer, assoc, "Cotisations", "10.00"),
    )
    assert simple.status_code == 201, simple.text

    manual = treasurer.post(
        f"/api/asso/{assoc}/ecritures",
        json={
            "journal_id": _journal_id(treasurer, assoc, "OD"),
            "date": TODAY,
            "libelle": "x",
            "lignes": [
                {"compte_id": _compte_id(treasurer, assoc, "512"), "debit": "5.00"},
                {"compte_id": _compte_id(treasurer, assoc, "756"), "credit": "5.00"},
            ],
        },
    )
    assert manual.status_code == 403


# --- Tenant isolation -----------------------------------------------------


def test_non_member_cannot_post_to_other_association():
    admin_a, _ = _admin_with_association("a@example.com", "alpha")
    _, assoc_b = _admin_with_association("b@example.com", "beta")

    # admin_a is not a member of B: 404, no existence leak.
    resp = admin_a.post(
        f"/api/asso/{assoc_b}/ecritures/simple",
        json={
            "categorie_id": "whatever",
            "compte_tresorerie_id": "whatever",
            "montant": "10.00",
            "date": TODAY,
        },
    )
    assert resp.status_code == 404


def test_cannot_reference_account_from_another_association():
    admin_a, assoc_a = _admin_with_association("a@example.com", "alpha")
    admin_b, assoc_b = _admin_with_association("b@example.com", "beta")

    # An account that exists, but in B — must not be usable from A.
    foreign_compte = _compte_id(admin_b, assoc_b, "512")
    resp = admin_a.post(
        f"/api/asso/{assoc_a}/ecritures/simple",
        json={
            "categorie_id": _categorie(admin_a, assoc_a, "Cotisations")["id"],
            "compte_tresorerie_id": foreign_compte,
            "montant": "10.00",
            "date": TODAY,
        },
    )
    assert resp.status_code == 400


def test_entry_id_is_scoped_to_its_association():
    admin_a, assoc_a = _admin_with_association("a@example.com", "alpha")
    admin_b, assoc_b = _admin_with_association("b@example.com", "beta")
    entry_a = _create_draft(admin_a, assoc_a)

    # B's admin cannot read A's entry through B's own (authorized) path.
    assert admin_b.get(f"/api/asso/{assoc_b}/ecritures/{entry_a}").status_code == 404
    # …nor through A's path (not a member of A).
    assert admin_b.get(f"/api/asso/{assoc_a}/ecritures/{entry_a}").status_code == 404


def test_entry_endpoints_require_authentication():
    assert _client().get("/api/asso/x/ecritures/y").status_code == 401
