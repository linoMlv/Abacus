"""Reporting reads: journal listing, trial balance and ledger, with isolation."""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from database import get_session
from main import _fastapi_app as app

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
        "/api/auth/associations", json={"name": name, "email": f"{name}@example.com"}
    )
    assert resp.status_code == 201, resp.text
    return client, resp.json()["id"]


def _categorie_id(client: TestClient, assoc_id: str, libelle: str) -> str:
    cats = client.get(f"/api/asso/{assoc_id}/categories").json()
    return next(c["id"] for c in cats if c["libelle"] == libelle)


def _compte_id(client: TestClient, assoc_id: str, numero: str) -> str:
    comptes = client.get(
        f"/api/asso/{assoc_id}/comptes", params={"search": numero}
    ).json()
    return next(c["id"] for c in comptes if c["numero"] == numero)


def _post_simple(client: TestClient, assoc_id: str, libelle: str, montant: str) -> None:
    resp = client.post(
        f"/api/asso/{assoc_id}/ecritures/simple",
        json={
            "categorie_id": _categorie_id(client, assoc_id, libelle),
            "compte_tresorerie_id": _compte_id(client, assoc_id, "512"),
            "montant": montant,
            "date": TODAY,
        },
    )
    assert resp.status_code == 201, resp.text


def _dec(value) -> Decimal:
    return Decimal(str(value))


def _seeded_books() -> tuple[TestClient, str]:
    """Association with one recette (150 cotisations) and one dépense (100 loyer)."""
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    _post_simple(admin, assoc, "Cotisations", "150.00")
    _post_simple(admin, assoc, "Locations", "100.00")
    return admin, assoc


# --- Journal --------------------------------------------------------------


def test_journal_lists_entries_newest_first():
    admin, assoc = _seeded_books()
    entries = admin.get(f"/api/asso/{assoc}/ecritures").json()
    assert [e["numero_piece"] for e in entries] == [2, 1]


def test_journal_can_filter_by_statut():
    admin, assoc = _seeded_books()
    entries = admin.get(f"/api/asso/{assoc}/ecritures").json()
    admin.post(f"/api/asso/{assoc}/ecritures/{entries[0]['id']}/validation")

    validated = admin.get(
        f"/api/asso/{assoc}/ecritures", params={"statut": "validee"}
    ).json()
    assert len(validated) == 1
    assert validated[0]["statut"] == "validee"


# --- Trial balance --------------------------------------------------------


def test_balance_is_globally_balanced_and_per_account_correct():
    admin, assoc = _seeded_books()
    rows = admin.get(f"/api/asso/{assoc}/balance").json()
    by_numero = {r["numero"]: r for r in rows}

    # 512 Banque: +150 (recette) debit, -100 (dépense) credit -> solde débiteur 50.
    assert _dec(by_numero["512"]["solde"]) == Decimal("50.00")
    # 756 Cotisations: credited 150 -> solde créditeur (négatif).
    assert _dec(by_numero["756"]["solde"]) == Decimal("-150.00")
    # 613 Locations: debited 100.
    assert _dec(by_numero["613"]["solde"]) == Decimal("100.00")

    # The whole balance balances: Σ débit = Σ crédit.
    total_debit = sum(_dec(r["total_debit"]) for r in rows)
    total_credit = sum(_dec(r["total_credit"]) for r in rows)
    assert total_debit == total_credit == Decimal("250.00")


# --- Ledger (grand livre) -------------------------------------------------


def test_grand_livre_has_running_balance():
    admin, assoc = _seeded_books()
    compte_512 = _compte_id(admin, assoc, "512")
    rows = admin.get(f"/api/asso/{assoc}/comptes/{compte_512}/grand-livre").json()

    assert len(rows) == 2
    # Chronological, with a cumulative balance: +150 then -100 => 150, 50.
    assert _dec(rows[0]["debit"]) == Decimal("150.00")
    assert _dec(rows[0]["solde"]) == Decimal("150.00")
    assert _dec(rows[1]["credit"]) == Decimal("100.00")
    assert _dec(rows[1]["solde"]) == Decimal("50.00")


# --- Isolation ------------------------------------------------------------


def test_reporting_is_tenant_isolated():
    _, assoc_a = _admin_with_association("a@example.com", "alpha")
    admin_b, assoc_b = _admin_with_association("b@example.com", "beta")
    foreign_compte = _compte_id(admin_b, assoc_b, "512")

    # admin_b is not a member of A: every reporting read is 404.
    assert admin_b.get(f"/api/asso/{assoc_a}/ecritures").status_code == 404
    assert admin_b.get(f"/api/asso/{assoc_a}/balance").status_code == 404

    # A foreign account id cannot be read through A's ledger via B either; and B
    # cannot read its own account through A's path (not a member of A).
    assert (
        admin_b.get(
            f"/api/asso/{assoc_a}/comptes/{foreign_compte}/grand-livre"
        ).status_code
        == 404
    )


def test_grand_livre_rejects_account_from_another_association():
    admin_a, assoc_a = _admin_with_association("a@example.com", "alpha")
    admin_b, assoc_b = _admin_with_association("b@example.com", "beta")
    foreign_compte = _compte_id(admin_b, assoc_b, "512")

    # The account exists, but in B: A must not be able to read it.
    resp = admin_a.get(f"/api/asso/{assoc_a}/comptes/{foreign_compte}/grand-livre")
    assert resp.status_code == 404


def test_reporting_requires_authentication():
    assert _client().get("/api/asso/x/balance").status_code == 401
