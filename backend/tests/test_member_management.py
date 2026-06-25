"""Member management: role/status changes, removal and the last-admin guard."""

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
    resp = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text


def _admin_with_association(email: str) -> tuple[TestClient, str]:
    client = _client()
    _register(client, email)
    _login(client, email)
    resp = client.post(
        "/api/auth/associations", json={"name": "Asso", "email": "asso@example.com"}
    )
    assert resp.status_code == 201, resp.text
    return client, resp.json()["id"]


def _add_member(
    session: Session, assoc_id: str, email: str, role: Role
) -> tuple[TestClient, str]:
    client = _client()
    user_id = _register(client, email)
    _login(client, email)
    session.add(Membership(user_id=user_id, association_id=assoc_id, role=role))
    session.commit()
    return client, user_id


def test_admin_can_change_member_role(session: Session):
    admin, assoc_id = _admin_with_association("admin@example.com")
    _, viewer_id = _add_member(session, assoc_id, "viewer@example.com", Role.VIEWER)

    resp = admin.patch(
        f"/api/asso/{assoc_id}/members/{viewer_id}", json={"role": "treasurer"}
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "treasurer"


def test_admin_can_suspend_and_member_loses_access(session: Session):
    admin, assoc_id = _admin_with_association("admin@example.com")
    member, member_id = _add_member(
        session, assoc_id, "member@example.com", Role.TREASURER
    )

    assert member.get(f"/api/asso/{assoc_id}").status_code == 200

    resp = admin.patch(
        f"/api/asso/{assoc_id}/members/{member_id}", json={"status": "suspended"}
    )
    assert resp.status_code == 200
    # Suspended -> 403 on the scoped route.
    assert member.get(f"/api/asso/{assoc_id}").status_code == 403


def test_admin_can_remove_member(session: Session):
    admin, assoc_id = _admin_with_association("admin@example.com")
    member, member_id = _add_member(
        session, assoc_id, "member@example.com", Role.VIEWER
    )

    assert admin.delete(f"/api/asso/{assoc_id}/members/{member_id}").status_code == 200
    # Removed -> no membership -> 404 (no existence leak).
    assert member.get(f"/api/asso/{assoc_id}").status_code == 404


def test_last_admin_cannot_be_demoted_suspended_or_removed(session: Session):
    admin, assoc_id = _admin_with_association("admin@example.com")
    admin_id = _register_id_of(admin)

    demote = admin.patch(
        f"/api/asso/{assoc_id}/members/{admin_id}", json={"role": "viewer"}
    )
    assert demote.status_code == 400

    suspend = admin.patch(
        f"/api/asso/{assoc_id}/members/{admin_id}", json={"status": "suspended"}
    )
    assert suspend.status_code == 400

    remove = admin.delete(f"/api/asso/{assoc_id}/members/{admin_id}")
    assert remove.status_code == 400


def test_admin_can_be_demoted_when_another_admin_exists(session: Session):
    admin, assoc_id = _admin_with_association("admin@example.com")
    admin_id = _register_id_of(admin)
    _, second_admin_id = _add_member(
        session, assoc_id, "admin2@example.com", Role.ADMIN
    )

    # With two admins, the first can be demoted.
    resp = admin.patch(
        f"/api/asso/{assoc_id}/members/{admin_id}", json={"role": "treasurer"}
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "treasurer"
    assert second_admin_id  # sanity


def test_non_admin_cannot_manage_members(session: Session):
    admin, assoc_id = _admin_with_association("admin@example.com")
    treasurer, treasurer_id = _add_member(
        session, assoc_id, "treasurer@example.com", Role.TREASURER
    )
    _, viewer_id = _add_member(session, assoc_id, "viewer@example.com", Role.VIEWER)

    assert (
        treasurer.patch(
            f"/api/asso/{assoc_id}/members/{viewer_id}", json={"role": "admin"}
        ).status_code
        == 403
    )
    assert (
        treasurer.delete(f"/api/asso/{assoc_id}/members/{viewer_id}").status_code == 403
    )


def test_managing_a_non_member_is_404(session: Session):
    admin, assoc_id = _admin_with_association("admin@example.com")
    assert (
        admin.patch(
            f"/api/asso/{assoc_id}/members/ghost", json={"role": "viewer"}
        ).status_code
        == 404
    )


def test_cannot_manage_members_of_another_association(session: Session):
    admin_a, assoc_a = _admin_with_association("admina@example.com")
    admin_b = _client()
    _register(admin_b, "adminb@example.com")
    _login(admin_b, "adminb@example.com")
    resp = admin_b.post(
        "/api/auth/associations",
        json={"name": "Asso B", "email": "assob@example.com"},
    )
    assoc_b = resp.json()["id"]
    _, victim_id = _add_member(session, assoc_b, "victim@example.com", Role.VIEWER)

    # Admin of A cannot touch a member of B: scoped route returns 404.
    assert (
        admin_a.patch(
            f"/api/asso/{assoc_b}/members/{victim_id}", json={"role": "admin"}
        ).status_code
        == 404
    )


def _register_id_of(client: TestClient) -> str:
    """Resolve the current client's user id via the session endpoint."""
    resp = client.get("/api/auth/session")
    assert resp.status_code == 200
    return resp.json()["user"]["id"]
