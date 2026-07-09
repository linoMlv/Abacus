"""Narrative annexe: default ANC rubric seeding, CRUD, reorder, RBAC, isolation.

The annexe rubrics are the human commentary of an exercice's comptes annuels.
The default ANC set is seeded lazily on first read; writing needs the dedicated
ANNEXE_MANAGE permission, reading only REPORT_VIEW. Everything is tenant-scoped.
"""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from database import get_session
from exports.data import annexe_data
from main import _fastapi_app as app
from models import DEFAULT_ANNEXE_RUBRIQUES, Membership, Role

PASSWORD = "password123"


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


def _member_with_role(
    session: Session, assoc: str, email: str, role: Role
) -> TestClient:
    client = _client()
    uid = client.post(
        "/api/auth/register",
        json={"email": email, "password": PASSWORD, "name": "M"},
    ).json()["id"]
    assert (
        client.post(
            "/api/auth/login", json={"email": email, "password": PASSWORD}
        ).status_code
        == 200
    )
    session.add(Membership(user_id=uid, association_id=assoc, role=role))
    session.commit()
    return client


def _exercice_id(client: TestClient, assoc: str) -> str:
    return client.get(f"/api/asso/{assoc}/exercices").json()[0]["id"]


def _rubriques(client: TestClient, assoc: str, ex: str) -> list[dict]:
    resp = client.get(f"/api/asso/{assoc}/exercices/{ex}/annexe")
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_first_read_seeds_the_default_anc_rubrics():
    client, assoc = _admin_with_association("seed@example.com", "alpha")
    ex = _exercice_id(client, assoc)

    rubriques = _rubriques(client, assoc, ex)
    assert [r["titre"] for r in rubriques] == list(DEFAULT_ANNEXE_RUBRIQUES)
    assert all(r["contenu"] == "" for r in rubriques)
    assert [r["ordre"] for r in rubriques] == list(range(len(DEFAULT_ANNEXE_RUBRIQUES)))


def test_reading_twice_does_not_duplicate_the_seed():
    client, assoc = _admin_with_association("seed2@example.com", "alpha")
    ex = _exercice_id(client, assoc)
    first = _rubriques(client, assoc, ex)
    second = _rubriques(client, assoc, ex)
    assert len(second) == len(first) == len(DEFAULT_ANNEXE_RUBRIQUES)


def test_add_edit_and_delete_a_rubrique():
    client, assoc = _admin_with_association("crud@example.com", "alpha")
    ex = _exercice_id(client, assoc)
    _rubriques(client, assoc, ex)  # seed

    created = client.post(
        f"/api/asso/{assoc}/exercices/{ex}/annexe",
        json={"titre": "Point particulier", "contenu": "Texte."},
    )
    assert created.status_code == 201, created.text
    rid = created.json()["id"]
    assert created.json()["ordre"] == len(DEFAULT_ANNEXE_RUBRIQUES)  # appended last

    edited = client.patch(
        f"/api/asso/{assoc}/annexe/{rid}", json={"contenu": "Mis à jour."}
    )
    assert edited.status_code == 200
    assert edited.json()["contenu"] == "Mis à jour."
    assert edited.json()["titre"] == "Point particulier"  # unchanged

    assert client.delete(f"/api/asso/{assoc}/annexe/{rid}").status_code == 204
    assert rid not in {r["id"] for r in _rubriques(client, assoc, ex)}


def test_empty_title_is_rejected():
    client, assoc = _admin_with_association("empty@example.com", "alpha")
    ex = _exercice_id(client, assoc)
    resp = client.post(
        f"/api/asso/{assoc}/exercices/{ex}/annexe",
        json={"titre": "   ", "contenu": "x"},
    )
    assert resp.status_code == 400


def test_reorder_rubriques():
    client, assoc = _admin_with_association("order@example.com", "alpha")
    ex = _exercice_id(client, assoc)
    ids = [r["id"] for r in _rubriques(client, assoc, ex)]
    reversed_ids = list(reversed(ids))

    resp = client.put(
        f"/api/asso/{assoc}/exercices/{ex}/annexe/ordre", json={"ids": reversed_ids}
    )
    assert resp.status_code == 200, resp.text
    assert [r["id"] for r in resp.json()] == reversed_ids


def test_viewer_can_read_but_not_write(session: Session):
    admin, assoc = _admin_with_association("vadmin@example.com", "alpha")
    ex = _exercice_id(admin, assoc)
    viewer = _member_with_role(session, assoc, "viewer@example.com", Role.VIEWER)

    assert viewer.get(f"/api/asso/{assoc}/exercices/{ex}/annexe").status_code == 200
    assert (
        viewer.post(
            f"/api/asso/{assoc}/exercices/{ex}/annexe",
            json={"titre": "x", "contenu": "y"},
        ).status_code
        == 403
    )


def test_treasurer_can_write(session: Session):
    admin, assoc = _admin_with_association("tadmin@example.com", "alpha")
    ex = _exercice_id(admin, assoc)
    treasurer = _member_with_role(session, assoc, "treso@example.com", Role.TREASURER)
    resp = treasurer.post(
        f"/api/asso/{assoc}/exercices/{ex}/annexe",
        json={"titre": "Engagement", "contenu": "Bail 2026."},
    )
    assert resp.status_code == 201, resp.text


def test_cross_tenant_exercice_is_404():
    admin_a, assoc_a = _admin_with_association("ta@example.com", "alpha")
    ex_a = _exercice_id(admin_a, assoc_a)
    other, _ = _admin_with_association("tb@example.com", "beta")
    assert other.get(f"/api/asso/{assoc_a}/exercices/{ex_a}/annexe").status_code == 404


def test_cross_tenant_rubrique_is_404():
    admin_a, assoc_a = _admin_with_association("ra@example.com", "alpha")
    ex_a = _exercice_id(admin_a, assoc_a)
    rid = _rubriques(admin_a, assoc_a, ex_a)[0]["id"]
    other, _ = _admin_with_association("rb@example.com", "beta")
    assert (
        other.patch(
            f"/api/asso/{assoc_a}/annexe/{rid}", json={"contenu": "x"}
        ).status_code
        == 404
    )


def test_filled_rubrics_appear_in_the_annexe_document(session: Session):
    client, assoc = _admin_with_association("pdf@example.com", "alpha")
    ex = _exercice_id(client, assoc)
    rid = _rubriques(client, assoc, ex)[0]["id"]
    client.patch(
        f"/api/asso/{assoc}/annexe/{rid}",
        json={"contenu": "Les comptes sont établis en partie double."},
    )

    data = annexe_data(session, assoc, date.today())
    titres = [n.titre for n in data.narrative]
    assert DEFAULT_ANNEXE_RUBRIQUES[0] in titres
    # Empty rubrics are not carried into the document.
    assert len(data.narrative) == 1
