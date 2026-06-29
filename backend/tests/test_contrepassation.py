"""Contre-passation (§10): reverse a validated entry, optionally annule-et-remplace.

A *validated* entry is immutable; correcting it goes through a reversal (extourne)
that swaps debit/credit, links back to the original and lands as a brouillon to
validate. With a ``remplacement`` payload, the same call also books the corrected
entry (annule-et-remplace). Gated by ``ENTRY_DELETE`` and tenant-scoped (A→B = 404).
"""

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


def _categorie_id(client: TestClient, assoc_id: str, libelle: str) -> str:
    cats = client.get(f"/api/asso/{assoc_id}/categories").json()
    return next(c["id"] for c in cats if c["libelle"] == libelle)


def _compte_id(client: TestClient, assoc_id: str, numero: str) -> str:
    comptes = client.get(
        f"/api/asso/{assoc_id}/comptes", params={"search": numero}
    ).json()
    return next(c["id"] for c in comptes if c["numero"] == numero)


def _simple_body(client: TestClient, assoc_id: str, montant: str) -> dict:
    return {
        "categorie_id": _categorie_id(client, assoc_id, "Cotisations"),
        "compte_tresorerie_id": _compte_id(client, assoc_id, "512"),
        "montant": montant,
        "date": TODAY,
        "libelle": "Cotisation",
    }


def _validated_simple(client: TestClient, assoc_id: str, montant: str) -> dict:
    created = client.post(
        f"/api/asso/{assoc_id}/ecritures/simple",
        json=_simple_body(client, assoc_id, montant),
    )
    assert created.status_code == 201, created.text
    entry = created.json()
    validated = client.post(f"/api/asso/{assoc_id}/ecritures/{entry['id']}/validation")
    assert validated.status_code == 200, validated.text
    return validated.json()


def test_contrepasser_validated_creates_a_linked_reversal_draft():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    original = _validated_simple(admin, assoc, "150.00")

    resp = admin.post(f"/api/asso/{assoc}/ecritures/{original['id']}/contrepassation")
    assert resp.status_code == 201, resp.text
    extourne = resp.json()["extourne"]
    assert extourne["origine"] == "extourne"
    assert extourne["statut"] == "brouillon"
    assert extourne["extourne_de_id"] == original["id"]
    assert extourne["numero_piece"] != original["numero_piece"]

    # Lines are the original's, with debit/credit swapped.
    orig_lines = {
        ligne["compte_id"]: (ligne["debit"], ligne["credit"])
        for ligne in original["lignes"]
    }
    for ligne in extourne["lignes"]:
        debit, credit = orig_lines[ligne["compte_id"]]
        assert ligne["debit"] == credit
        assert ligne["credit"] == debit

    # The original is untouched — still validated, never edited.
    again = admin.get(f"/api/asso/{assoc}/ecritures/{original['id']}").json()
    assert again["statut"] == "validee"


def test_contrepasser_a_draft_is_409():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    created = admin.post(
        f"/api/asso/{assoc}/ecritures/simple",
        json=_simple_body(admin, assoc, "150.00"),
    ).json()

    resp = admin.post(f"/api/asso/{assoc}/ecritures/{created['id']}/contrepassation")
    assert resp.status_code == 409, resp.text


def test_contrepasser_twice_is_409():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    original = _validated_simple(admin, assoc, "150.00")
    first = admin.post(f"/api/asso/{assoc}/ecritures/{original['id']}/contrepassation")
    assert first.status_code == 201, first.text

    second = admin.post(f"/api/asso/{assoc}/ecritures/{original['id']}/contrepassation")
    assert second.status_code == 409, second.text


def test_annule_et_remplace_books_reversal_and_corrected_entry():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    original = _validated_simple(admin, assoc, "150.00")

    resp = admin.post(
        f"/api/asso/{assoc}/ecritures/{original['id']}/contrepassation",
        json={"remplacement": {"simple": _simple_body(admin, assoc, "200.00")}},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["extourne"]["origine"] == "extourne"
    remplacement = body["remplacement"]
    assert remplacement is not None
    assert remplacement["origine"] == "saisie_simple"
    assert remplacement["statut"] == "brouillon"
    # The corrected entry carries the new amount.
    debits = [ligne["debit"] for ligne in remplacement["lignes"]]
    assert "200.00" in debits


def test_remplacement_must_match_the_original_origine():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    original = _validated_simple(admin, assoc, "150.00")

    # The original is a saisie_simple; a virement replacement does not match → 400.
    resp = admin.post(
        f"/api/asso/{assoc}/ecritures/{original['id']}/contrepassation",
        json={
            "remplacement": {
                "virement": {
                    "compte_source_id": _compte_id(admin, assoc, "512"),
                    "compte_destination_id": _compte_id(admin, assoc, "531"),
                    "montant": "10.00",
                    "date": TODAY,
                }
            }
        },
    )
    assert resp.status_code == 400, resp.text


def test_contrepasser_other_tenant_entry_is_404():
    admin_a, assoc_a = _admin_with_association("a@example.com", "alpha")
    original = _validated_simple(admin_a, assoc_a, "150.00")
    admin_b, assoc_b = _admin_with_association("b@example.com", "beta")

    resp = admin_b.post(
        f"/api/asso/{assoc_b}/ecritures/{original['id']}/contrepassation"
    )
    assert resp.status_code == 404, resp.text


def test_contrepasser_requires_entry_delete(session: Session):
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    original = _validated_simple(admin, assoc, "150.00")
    viewer = _member_client(session, assoc, "viewer@example.com", Role.VIEWER)

    resp = viewer.post(f"/api/asso/{assoc}/ecritures/{original['id']}/contrepassation")
    assert resp.status_code == 403, resp.text
