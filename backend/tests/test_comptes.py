"""Guided chart-of-accounts management: creation, rename, archiving, guards.

The chart of accounts is structural: a wrong number distorts the bilan and the
FEC. So creation is *guided* (the number is proposed from a rubrique), the number
is immutable once created, archiving never deletes, and the accounts the engine
depends on (report à nouveau, résultat, TVA…) and the treasury accounts (managed
in Trésorerie) refuse to be touched here.
"""

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


def _comptes(client: TestClient, assoc: str, **params) -> list[dict]:
    resp = client.get(f"/api/asso/{assoc}/comptes", params=params)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _compte_by_numero(client: TestClient, assoc: str, numero: str) -> dict:
    return next(
        c
        for c in _comptes(client, assoc, include_inactive=True)
        if c["numero"] == numero
    )


# --- Création guidée ---------------------------------------------------------


def test_create_with_explicit_numero_derives_the_classe():
    client, assoc = _admin_with_association("a@example.com", "AssoA")

    resp = client.post(
        f"/api/asso/{assoc}/comptes",
        json={"numero": "6135", "libelle": "Location de salle", "type": "charge"},
    )

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["numero"] == "6135"
    assert body["classe"] == 6
    assert body["type"] == "charge"
    assert body["is_active"] is True
    assert any(c["numero"] == "6135" for c in _comptes(client, assoc))


def test_create_under_a_rubrique_proposes_the_next_free_number():
    """Guided path: the volunteer picks the rubrique (606), we number the child."""
    client, assoc = _admin_with_association("b@example.com", "AssoB")

    first = client.post(
        f"/api/asso/{assoc}/comptes",
        json={"prefixe": "606", "libelle": "Petit équipement", "type": "charge"},
    )
    second = client.post(
        f"/api/asso/{assoc}/comptes",
        json={"prefixe": "606", "libelle": "Produits d'entretien", "type": "charge"},
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["numero"] == "6061"
    assert second.json()["numero"] == "6062"


def test_create_requires_a_numero_or_a_rubrique():
    client, assoc = _admin_with_association("c@example.com", "AssoC")

    resp = client.post(
        f"/api/asso/{assoc}/comptes",
        json={"libelle": "Sans numéro", "type": "charge"},
    )

    assert resp.status_code == 400


def test_create_rejects_a_duplicate_numero():
    client, assoc = _admin_with_association("d@example.com", "AssoD")

    resp = client.post(
        f"/api/asso/{assoc}/comptes",
        json={"numero": "6064", "libelle": "Doublon", "type": "charge"},
    )

    assert resp.status_code == 400
    assert "existe" in resp.json()["detail"].lower()


def test_create_rejects_a_type_incoherent_with_the_classe():
    client, assoc = _admin_with_association("e@example.com", "AssoE")

    resp = client.post(
        f"/api/asso/{assoc}/comptes",
        json={"numero": "6199", "libelle": "Charge mal typée", "type": "produit"},
    )

    assert resp.status_code == 400
    assert "classe 6" in resp.json()["detail"]


def test_create_rejects_a_malformed_numero():
    client, assoc = _admin_with_association("f@example.com", "AssoF")

    for numero in ("61A", "9", "0612", "6"):
        resp = client.post(
            f"/api/asso/{assoc}/comptes",
            json={"numero": numero, "libelle": "Bidon", "type": "charge"},
        )
        assert resp.status_code == 400, numero


def test_create_requires_the_account_permission(session: Session):
    client, assoc = _admin_with_association("g@example.com", "AssoG")
    treasurer = _member_client(session, assoc, "tres@example.com", Role.TREASURER)

    resp = treasurer.post(
        f"/api/asso/{assoc}/comptes",
        json={"numero": "6135", "libelle": "Location", "type": "charge"},
    )

    assert resp.status_code == 403
    assert not any(c["numero"] == "6135" for c in _comptes(client, assoc))


# --- Édition & archivage -----------------------------------------------------


def test_rename_keeps_the_number():
    client, assoc = _admin_with_association("h@example.com", "AssoH")
    compte = _compte_by_numero(client, assoc, "6064")

    resp = client.patch(
        f"/api/asso/{assoc}/comptes/{compte['id']}",
        json={"libelle": "Fournitures de bureau"},
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["libelle"] == "Fournitures de bureau"
    assert resp.json()["numero"] == "6064"


def test_archive_hides_the_account_without_deleting_it():
    client, assoc = _admin_with_association("i@example.com", "AssoI")
    created = client.post(
        f"/api/asso/{assoc}/comptes",
        json={"numero": "6135", "libelle": "Location de salle", "type": "charge"},
    ).json()

    resp = client.patch(
        f"/api/asso/{assoc}/comptes/{created['id']}", json={"is_active": False}
    )

    assert resp.status_code == 200, resp.text
    assert not any(c["numero"] == "6135" for c in _comptes(client, assoc))
    archived = _compte_by_numero(client, assoc, "6135")
    assert archived["is_active"] is False


def test_structural_accounts_cannot_be_archived():
    """110/120/44571… are wired into the engine (closing, VAT): archiving them
    would break the closing entry, so it is refused."""
    client, assoc = _admin_with_association("j@example.com", "AssoJ")

    for numero in ("110", "120", "44571"):
        compte = _compte_by_numero(client, assoc, numero)
        resp = client.patch(
            f"/api/asso/{assoc}/comptes/{compte['id']}", json={"is_active": False}
        )
        assert resp.status_code == 409, numero


def test_an_account_used_by_an_active_categorie_cannot_be_archived():
    client, assoc = _admin_with_association("k@example.com", "AssoK")
    categorie = client.get(f"/api/asso/{assoc}/categories").json()[0]
    compte_id = categorie["compte_id"]

    resp = client.patch(
        f"/api/asso/{assoc}/comptes/{compte_id}", json={"is_active": False}
    )

    assert resp.status_code == 409
    assert "catégorie" in resp.json()["detail"].lower()


def test_treasury_accounts_are_managed_from_tresorerie_only():
    client, assoc = _admin_with_association("l@example.com", "AssoL")
    banque = _compte_by_numero(client, assoc, "512")

    resp = client.patch(
        f"/api/asso/{assoc}/comptes/{banque['id']}", json={"libelle": "Renommé"}
    )

    assert resp.status_code == 409
    assert "trésorerie" in resp.json()["detail"].lower()


def test_creating_a_treasury_numbered_account_is_refused():
    """A 512x/531x account is a treasury account: it must carry its type, IBAN and
    colour, so it is created from Trésorerie — not silently here."""
    client, assoc = _admin_with_association("m@example.com", "AssoM")

    resp = client.post(
        f"/api/asso/{assoc}/comptes",
        json={"numero": "5129", "libelle": "Banque bis", "type": "actif"},
    )

    assert resp.status_code == 409
    assert "trésorerie" in resp.json()["detail"].lower()


def test_update_requires_the_account_permission(session: Session):
    client, assoc = _admin_with_association("n@example.com", "AssoN")
    treasurer = _member_client(session, assoc, "tres2@example.com", Role.TREASURER)
    compte = _compte_by_numero(client, assoc, "6064")

    resp = treasurer.patch(
        f"/api/asso/{assoc}/comptes/{compte['id']}", json={"libelle": "Nope"}
    )

    assert resp.status_code == 403


# --- Isolation ---------------------------------------------------------------


def test_an_account_of_another_association_is_not_reachable():
    client_a, assoc_a = _admin_with_association("o@example.com", "AssoO")
    client_b, assoc_b = _admin_with_association("p@example.com", "AssoP")
    compte_b = _compte_by_numero(client_b, assoc_b, "6064")

    resp = client_a.patch(
        f"/api/asso/{assoc_a}/comptes/{compte_b['id']}", json={"libelle": "Fuite"}
    )

    assert resp.status_code == 404
