"""Bank import & reconciliation endpoints: import, lettrage, create-from-line,
suggestions, isolation and RBAC."""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from database import get_session
from main import _fastapi_app as app
from models import Membership, Role

PASSWORD = "password123"

CSV_TWO = (
    "Date;Libelle;Montant\n"
    "15/06/2026;Cotisation Dupont;150,00\n"
    "18/06/2026;Frais tenue de compte;-8,00\n"
)
CSV_ONE = "Date;Libelle;Montant\n15/06/2026;Cotisation Dupont;150,00\n"


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


def _member_client(
    session: Session, assoc_id: str, email: str, role: Role
) -> TestClient:
    client = _client()
    uid = _register(client, email)
    _login(client, email)
    session.add(Membership(user_id=uid, association_id=assoc_id, role=role))
    session.commit()
    return client


def _treasury_id(client: TestClient, assoc: str, numero: str) -> str:
    rows = client.get(f"/api/asso/{assoc}/tresorerie").json()
    return next(r["id"] for r in rows if r["numero"] == numero)


def _categorie_id(client: TestClient, assoc: str, libelle: str) -> str:
    cats = client.get(f"/api/asso/{assoc}/categories").json()
    return next(c["id"] for c in cats if c["libelle"] == libelle)


def _import(client: TestClient, assoc: str, compte_id: str, content: str, **overrides):
    data = {
        "compte_id": compte_id,
        "date_col": "0",
        "libelle_col": "1",
        "montant_col": "2",
    }
    data.update(overrides)
    return client.post(
        f"/api/asso/{assoc}/banque/import",
        data=data,
        files={"fichier": ("releve.csv", content.encode("utf-8"), "text/csv")},
    )


def _lignes(client: TestClient, assoc: str) -> list[dict]:
    resp = client.get(f"/api/asso/{assoc}/banque/lignes")
    assert resp.status_code == 200, resp.text
    return resp.json()


def _dec(value) -> Decimal:
    return Decimal(str(value))


def _post_simple(client, assoc, categorie: str, compte_id: str, montant: str) -> str:
    resp = client.post(
        f"/api/asso/{assoc}/ecritures/simple",
        json={
            "categorie_id": _categorie_id(client, assoc, categorie),
            "compte_tresorerie_id": compte_id,
            "montant": montant,
            "date": "2026-06-15",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# --- Import ---------------------------------------------------------------


def test_import_creates_signed_bank_lines():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    bank = _treasury_id(admin, assoc, "512")

    resp = _import(admin, assoc, bank, CSV_TWO)
    assert resp.status_code == 201, resp.text
    assert resp.json()["nb_lignes"] == 2

    by_libelle = {row["libelle"]: row for row in _lignes(admin, assoc)}
    assert _dec(by_libelle["Cotisation Dupont"]["montant"]) == Decimal("150.00")
    assert _dec(by_libelle["Frais tenue de compte"]["montant"]) == Decimal("-8.00")
    assert all(row["statut"] == "non_rapproche" for row in by_libelle.values())
    assert all(row["compte_id"] == bank for row in by_libelle.values())


def test_import_onto_unknown_account_is_404():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    resp = _import(admin, assoc, "does-not-exist", CSV_ONE)
    assert resp.status_code == 404


def test_import_rejects_a_malformed_row():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    bank = _treasury_id(admin, assoc, "512")
    resp = _import(admin, assoc, bank, "Date;Libelle;Montant\nnot-a-date;X;10,00\n")
    assert resp.status_code == 400


# --- Create the missing entry from a line ---------------------------------


def test_create_entry_from_line_lettres_it():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    bank = _treasury_id(admin, assoc, "512")
    _import(admin, assoc, bank, CSV_ONE)
    ligne = _lignes(admin, assoc)[0]

    resp = admin.post(
        f"/api/asso/{assoc}/banque/lignes/{ligne['id']}/creer-ecriture",
        json={"categorie_id": _categorie_id(admin, assoc, "Cotisations")},
    )
    assert resp.status_code == 201, resp.text
    entry = resp.json()
    assert entry["origine"] == "saisie_simple"
    # The bank account is debited by the inflow amount.
    debit_512 = next(
        _dec(row["debit"]) for row in entry["lignes"] if row["compte_id"] == bank
    )
    assert debit_512 == Decimal("150.00")

    # The line is now reconciled to the created entry.
    ligne = _lignes(admin, assoc)[0]
    assert ligne["statut"] == "rapproche"
    assert ligne["ecriture_id"] == entry["id"]


def test_create_entry_with_wrong_sens_is_rejected():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    bank = _treasury_id(admin, assoc, "512")
    _import(admin, assoc, bank, CSV_ONE)  # +150 inflow → expects a recette category
    ligne = _lignes(admin, assoc)[0]

    resp = admin.post(
        f"/api/asso/{assoc}/banque/lignes/{ligne['id']}/creer-ecriture",
        json={"categorie_id": _categorie_id(admin, assoc, "Frais bancaires")},
    )
    assert resp.status_code == 400


# --- Lettrer an existing entry --------------------------------------------


def test_suggestions_and_rapprocher_existing_entry():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    bank = _treasury_id(admin, assoc, "512")
    entry_id = _post_simple(admin, assoc, "Cotisations", bank, "150.00")
    _import(admin, assoc, bank, CSV_ONE)
    ligne = _lignes(admin, assoc)[0]

    suggestions = admin.get(
        f"/api/asso/{assoc}/banque/lignes/{ligne['id']}/suggestions"
    ).json()
    assert any(s["ecriture_id"] == entry_id for s in suggestions)

    resp = admin.post(
        f"/api/asso/{assoc}/banque/lignes/{ligne['id']}/rapprocher",
        json={"ecriture_id": entry_id},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["statut"] == "rapproche"
    assert resp.json()["ecriture_id"] == entry_id


def test_rapprocher_entry_not_touching_the_account_is_rejected():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    bank = _treasury_id(admin, assoc, "512")
    cash = _treasury_id(admin, assoc, "531")
    # An entry that moves the cash account only, not the bank.
    entry_id = _post_simple(admin, assoc, "Cotisations", cash, "150.00")
    _import(admin, assoc, bank, CSV_ONE)
    ligne = _lignes(admin, assoc)[0]

    resp = admin.post(
        f"/api/asso/{assoc}/banque/lignes/{ligne['id']}/rapprocher",
        json={"ecriture_id": entry_id},
    )
    assert resp.status_code == 400


def test_an_entry_cannot_be_reconciled_twice():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    bank = _treasury_id(admin, assoc, "512")
    entry_id = _post_simple(admin, assoc, "Cotisations", bank, "150.00")
    _import(admin, assoc, bank, CSV_ONE + "16/06/2026;Autre;150,00\n")
    lignes = _lignes(admin, assoc)

    first = admin.post(
        f"/api/asso/{assoc}/banque/lignes/{lignes[0]['id']}/rapprocher",
        json={"ecriture_id": entry_id},
    )
    assert first.status_code == 200
    second = admin.post(
        f"/api/asso/{assoc}/banque/lignes/{lignes[1]['id']}/rapprocher",
        json={"ecriture_id": entry_id},
    )
    assert second.status_code == 409


def test_delettrer_returns_line_to_non_rapproche():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    bank = _treasury_id(admin, assoc, "512")
    _import(admin, assoc, bank, CSV_ONE)
    ligne = _lignes(admin, assoc)[0]
    admin.post(
        f"/api/asso/{assoc}/banque/lignes/{ligne['id']}/creer-ecriture",
        json={"categorie_id": _categorie_id(admin, assoc, "Cotisations")},
    )

    resp = admin.post(f"/api/asso/{assoc}/banque/lignes/{ligne['id']}/delettrer")
    assert resp.status_code == 200, resp.text
    assert resp.json()["statut"] == "non_rapproche"
    assert resp.json()["ecriture_id"] is None


def test_ignorer_and_bring_back_a_line():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    bank = _treasury_id(admin, assoc, "512")
    _import(admin, assoc, bank, CSV_ONE)
    ligne = _lignes(admin, assoc)[0]

    ignored = admin.post(f"/api/asso/{assoc}/banque/lignes/{ligne['id']}/ignorer")
    assert ignored.status_code == 200
    assert ignored.json()["statut"] == "ignore"

    back = admin.post(
        f"/api/asso/{assoc}/banque/lignes/{ligne['id']}/ignorer?ignore=false"
    )
    assert back.json()["statut"] == "non_rapproche"


# --- Isolation & RBAC -----------------------------------------------------


def test_cross_tenant_line_is_not_reachable():
    admin_a, assoc_a = _admin_with_association("a@example.com", "alpha")
    admin_b, assoc_b = _admin_with_association("b@example.com", "beta")
    bank_b = _treasury_id(admin_b, assoc_b, "512")
    _import(admin_b, assoc_b, bank_b, CSV_ONE)
    ligne_b = _lignes(admin_b, assoc_b)[0]

    # A reconciling B's line through A's own scope: the id is not A's → 404.
    resp = admin_a.post(f"/api/asso/{assoc_a}/banque/lignes/{ligne_b['id']}/delettrer")
    assert resp.status_code == 404
    # A reaching into B's association at all: not a member → 404.
    assert admin_a.get(f"/api/asso/{assoc_b}/banque/lignes").status_code == 404


def test_viewer_cannot_import(session: Session):
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    bank = _treasury_id(admin, assoc, "512")
    viewer = _member_client(session, assoc, "viewer@example.com", Role.VIEWER)
    resp = _import(viewer, assoc, bank, CSV_ONE)
    assert resp.status_code == 403
