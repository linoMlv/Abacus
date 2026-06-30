"""Official figures exclude drafts.

Only validated entries — plus opening balances, which are validated on creation —
feed the balances, treasury soldes, the ledger and the synthesis. A draft is
visible in the journal (a transparent register) but never moves a reported figure
until it is validated.
"""

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


def _compte_id(client: TestClient, assoc: str, numero: str) -> str:
    rows = client.get(f"/api/asso/{assoc}/comptes", params={"search": numero}).json()
    return next(c["id"] for c in rows if c["numero"] == numero)


def _post_simple(client: TestClient, assoc: str, libelle: str, montant: str) -> str:
    resp = client.post(
        f"/api/asso/{assoc}/ecritures/simple",
        json={
            "categorie_id": _categorie_id(client, assoc, libelle),
            "compte_tresorerie_id": _compte_id(client, assoc, "512"),
            "montant": montant,
            "date": TODAY,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _validate(client: TestClient, assoc: str, ecriture_id: str) -> None:
    assert (
        client.post(f"/api/asso/{assoc}/ecritures/{ecriture_id}/validation").status_code
        == 200
    )


def _balance(client: TestClient, assoc: str) -> dict[str, dict]:
    return {r["numero"]: r for r in client.get(f"/api/asso/{assoc}/balance").json()}


def _treasury_solde(client: TestClient, assoc: str, numero: str = "512") -> Decimal:
    compte_id = _compte_id(client, assoc, numero)
    rows = client.get(f"/api/asso/{assoc}/tresorerie").json()
    return next(Decimal(r["solde"]) for r in rows if r["id"] == compte_id)


# --- Drafts excluded from figures ----------------------------------------- #


def test_draft_is_excluded_from_the_balance_until_validated():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    ecriture_id = _post_simple(admin, assoc, "Cotisations", "150.00")

    # A draft moves nothing: the touched accounts do not appear in the balance.
    assert "512" not in _balance(admin, assoc)

    _validate(admin, assoc, ecriture_id)
    balance = _balance(admin, assoc)
    assert Decimal(balance["512"]["solde"]) == Decimal("150.00")
    assert Decimal(balance["756"]["solde"]) == Decimal("-150.00")


def test_draft_does_not_move_the_treasury_solde():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    ecriture_id = _post_simple(admin, assoc, "Cotisations", "150.00")

    assert _treasury_solde(admin, assoc) == Decimal("0.00")
    _validate(admin, assoc, ecriture_id)
    assert _treasury_solde(admin, assoc) == Decimal("150.00")


def test_draft_is_excluded_from_the_grand_livre_until_validated():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    ecriture_id = _post_simple(admin, assoc, "Cotisations", "150.00")
    compte_512 = _compte_id(admin, assoc, "512")

    ledger = admin.get(f"/api/asso/{assoc}/comptes/{compte_512}/grand-livre").json()
    assert ledger == []

    _validate(admin, assoc, ecriture_id)
    ledger = admin.get(f"/api/asso/{assoc}/comptes/{compte_512}/grand-livre").json()
    assert len(ledger) == 1
    assert Decimal(ledger[0]["solde"]) == Decimal("150.00")


def test_draft_is_excluded_from_the_synthese_resultat():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    ecriture_id = _post_simple(admin, assoc, "Cotisations", "150.00")

    synthese = admin.get(f"/api/asso/{assoc}/synthese").json()
    assert Decimal(synthese["resultat"]["recettes"]) == Decimal("0.00")

    _validate(admin, assoc, ecriture_id)
    synthese = admin.get(f"/api/asso/{assoc}/synthese").json()
    assert Decimal(synthese["resultat"]["recettes"]) == Decimal("150.00")


def test_draft_still_shows_in_the_journal_register():
    # The journal is a transparent register: a draft is listed (with its statut),
    # only the *figures* exclude it.
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    _post_simple(admin, assoc, "Cotisations", "150.00")
    entries = admin.get(f"/api/asso/{assoc}/ecritures").json()
    assert len(entries) == 1
    assert entries[0]["statut"] == "brouillon"


# --- Opening balances are validated on creation --------------------------- #


def test_opening_balance_counts_immediately_as_validated():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    compte_512 = _compte_id(admin, assoc, "512")
    resp = admin.post(
        f"/api/asso/{assoc}/tresorerie/{compte_512}/solde-initial",
        json={"montant": "500.00", "date_solde_initial": TODAY},
    )
    assert resp.status_code == 200, resp.text

    # No validation step needed: the opening balance is official right away.
    assert _treasury_solde(admin, assoc) == Decimal("500.00")
    validated = admin.get(
        f"/api/asso/{assoc}/ecritures", params={"statut": "validee"}
    ).json()
    assert any(e["origine"] == "a_nouveau" for e in validated)


def test_opening_balance_is_immutable_once_set():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    compte_512 = _compte_id(admin, assoc, "512")
    assert (
        admin.post(
            f"/api/asso/{assoc}/tresorerie/{compte_512}/solde-initial",
            json={"montant": "500.00", "date_solde_initial": TODAY},
        ).status_code
        == 200
    )

    # A validated opening balance can no longer be edited in place (409): adjusting
    # it goes through a contre-passation, like any validated entry.
    resp = admin.post(
        f"/api/asso/{assoc}/tresorerie/{compte_512}/solde-initial",
        json={"montant": "600.00", "date_solde_initial": TODAY},
    )
    assert resp.status_code == 409
