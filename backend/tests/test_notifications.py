"""The notification bell (C28): what needs *me*, per person, per association.

Notifications are derived from the association's real state and filtered by what
the reader may act on — an exercice to close only reaches whoever may close one.
They are deduplicated (one per subject), they disappear when the situation they
reported is settled, and a read one stays read.
"""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from database import get_session
from main import _fastapi_app as app
from models import Ecriture, Exercice, Membership, Role

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


def _categorie_id(client: TestClient, assoc: str, libelle: str) -> str:
    return next(
        c["id"]
        for c in client.get(f"/api/asso/{assoc}/categories").json()
        if c["libelle"] == libelle
    )


def _treso_id(client: TestClient, assoc: str, numero: str) -> str:
    return next(
        c["id"]
        for c in client.get(f"/api/asso/{assoc}/tresorerie").json()
        if c["numero"] == numero
    )


def _post_draft(client: TestClient, assoc: str) -> str:
    resp = client.post(
        f"/api/asso/{assoc}/ecritures/simple",
        json={
            "categorie_id": _categorie_id(client, assoc, "Cotisations"),
            "compte_tresorerie_id": _treso_id(client, assoc, "512"),
            "montant": "150.00",
            "date": date.today().isoformat(),
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _notifications(client: TestClient, assoc: str) -> dict:
    resp = client.get(f"/api/asso/{assoc}/notifications")
    assert resp.status_code == 200, resp.text
    return resp.json()


# --- Ce qui arrive dans la cloche -------------------------------------------


def test_an_empty_association_rings_nothing():
    admin, assoc = _admin_with_association("a@example.com", "alpha")

    body = _notifications(admin, assoc)

    assert body["non_lues"] == 0
    assert body["notifications"] == []


def test_a_draft_from_someone_else_asks_whoever_can_validate(session: Session):
    admin, assoc = _admin_with_association("b@example.com", "beta")
    treasurer = _member_client(session, assoc, "tres@example.com", Role.TREASURER)
    _post_draft(treasurer, assoc)

    body = _notifications(admin, assoc)

    assert body["non_lues"] == 1
    notification = body["notifications"][0]
    assert notification["type"] == "ecriture_a_valider"
    assert "/journal" in notification["lien"]


def test_my_own_draft_is_not_news_to_me():
    admin, assoc = _admin_with_association("c@example.com", "gamma")
    _post_draft(admin, assoc)

    assert _notifications(admin, assoc)["non_lues"] == 0


def test_a_treasurer_is_not_told_to_validate_what_they_may_not_validate(
    session: Session,
):
    admin, assoc = _admin_with_association("d@example.com", "delta")
    treasurer = _member_client(session, assoc, "tres2@example.com", Role.TREASURER)
    _post_draft(admin, assoc)

    # The treasurer holds no ENTRY_VALIDATE: the draft is not theirs to act on.
    assert _notifications(treasurer, assoc)["non_lues"] == 0


def test_an_overdue_exercice_reaches_whoever_may_close_it(session: Session):
    admin, assoc = _admin_with_association("e@example.com", "epsilon")
    exercice = session.exec(
        select(Exercice).where(Exercice.association_id == assoc)
    ).one()
    exercice.date_fin = date.today() - timedelta(days=1)
    session.add(exercice)
    session.commit()

    types = [n["type"] for n in _notifications(admin, assoc)["notifications"]]

    assert "exercice_a_cloturer" in types


# --- Cycle de vie ------------------------------------------------------------


def test_the_same_subject_never_rings_twice(session: Session):
    admin, assoc = _admin_with_association("f@example.com", "zeta")
    treasurer = _member_client(session, assoc, "tres3@example.com", Role.TREASURER)
    _post_draft(treasurer, assoc)

    _notifications(admin, assoc)
    body = _notifications(admin, assoc)

    assert len(body["notifications"]) == 1


def test_settling_the_situation_clears_the_notification(session: Session):
    admin, assoc = _admin_with_association("g@example.com", "eta")
    treasurer = _member_client(session, assoc, "tres4@example.com", Role.TREASURER)
    ecriture_id = _post_draft(treasurer, assoc)
    assert _notifications(admin, assoc)["non_lues"] == 1

    assert (
        admin.post(f"/api/asso/{assoc}/ecritures/{ecriture_id}/validation").status_code
        == 200
    )

    assert _notifications(admin, assoc)["non_lues"] == 0


def test_marking_one_as_read_leaves_it_read(session: Session):
    admin, assoc = _admin_with_association("h@example.com", "theta")
    treasurer = _member_client(session, assoc, "tres5@example.com", Role.TREASURER)
    _post_draft(treasurer, assoc)
    notification = _notifications(admin, assoc)["notifications"][0]

    resp = admin.post(f"/api/asso/{assoc}/notifications/{notification['id']}/lecture")

    assert resp.status_code == 200, resp.text
    body = _notifications(admin, assoc)
    assert body["non_lues"] == 0
    assert len(body["notifications"]) == 1  # still listed, just not unread


def test_marking_everything_as_read(session: Session):
    admin, assoc = _admin_with_association("i@example.com", "iota")
    treasurer = _member_client(session, assoc, "tres6@example.com", Role.TREASURER)
    _post_draft(treasurer, assoc)
    _post_draft(treasurer, assoc)
    assert _notifications(admin, assoc)["non_lues"] == 2

    assert admin.post(f"/api/asso/{assoc}/notifications/lecture").status_code == 200

    assert _notifications(admin, assoc)["non_lues"] == 0


# --- Isolation ---------------------------------------------------------------


def test_notifications_never_cross_associations(session: Session):
    admin_a, assoc_a = _admin_with_association("j@example.com", "kappa")
    admin_b, assoc_b = _admin_with_association("k@example.com", "lambda")
    treasurer = _member_client(session, assoc_a, "tres7@example.com", Role.TREASURER)
    _post_draft(treasurer, assoc_a)

    assert _notifications(admin_a, assoc_a)["non_lues"] == 1
    assert _notifications(admin_b, assoc_b)["non_lues"] == 0
    assert admin_b.get(f"/api/asso/{assoc_a}/notifications").status_code == 404


def test_another_persons_notification_cannot_be_marked_read(session: Session):
    admin, assoc = _admin_with_association("l@example.com", "mu")
    accountant = _member_client(session, assoc, "expert@example.com", Role.ACCOUNTANT)
    other = _member_client(session, assoc, "tres8@example.com", Role.TREASURER)
    _post_draft(other, assoc)
    mine = _notifications(admin, assoc)["notifications"][0]

    # The accountant also gets one (they may validate) — but not *this* row.
    resp = accountant.post(f"/api/asso/{assoc}/notifications/{mine['id']}/lecture")

    assert resp.status_code == 404
    assert (
        session.exec(select(Ecriture).where(Ecriture.association_id == assoc))
        .first()
        .statut.value
        == "brouillon"
    )
