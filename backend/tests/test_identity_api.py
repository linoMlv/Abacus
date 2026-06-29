"""End-to-end security tests for the V3 identity & access API.

The focus is tenant isolation and RBAC — the contract that "a member of A can
never reach B". Each user gets its own client (own cookie jar); memberships not
yet creatable via the API (invitations come later) are inserted through the
``session`` fixture, which the app shares.
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from authz import Permission
from database import get_session
from main import _fastapi_app as app
from models import Membership, MembershipStatus, Role

PASSWORD = "password123"


@pytest.fixture(autouse=True)
def _use_test_session(session: Session):
    """Route every client built in this module through the shared test session.

    Tests construct their own clients (one cookie jar per user), so the
    get_session override must be active regardless of which fixtures a test
    declares.
    """
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


def _login(client: TestClient, email: str) -> dict:
    resp = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _create_association(client: TestClient, name: str, email: str) -> str:
    resp = client.post("/api/auth/associations", json={"name": name, "email": email})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _logged_in(email: str) -> TestClient:
    client = _client()
    _register(client, email)
    _login(client, email)
    return client


# --------------------------------------------------------------------------- #
# Account & session
# --------------------------------------------------------------------------- #
def test_register_then_login_returns_session(client: TestClient):
    _register(client, "alice@example.com")
    body = _login(client, "alice@example.com")
    assert body["user"]["email"] == "alice@example.com"
    assert body["associations"] == []

    session = client.get("/api/auth/session")
    assert session.status_code == 200
    assert session.json()["user"]["email"] == "alice@example.com"


def test_email_is_normalized(client: TestClient):
    _register(client, "Mixed.Case@Example.com")
    # Login with a different casing must resolve the same account.
    body = _login(client, "mixed.case@example.com")
    assert body["user"]["email"] == "mixed.case@example.com"


def test_login_wrong_password_is_401(client: TestClient):
    _register(client, "bob@example.com")
    resp = client.post(
        "/api/auth/login", json={"email": "bob@example.com", "password": "nope"}
    )
    assert resp.status_code == 401


def test_duplicate_registration_is_rejected_generically(client: TestClient):
    _register(client, "dup@example.com")
    resp = client.post(
        "/api/auth/register",
        json={"email": "dup@example.com", "password": PASSWORD, "name": "X"},
    )
    assert resp.status_code == 400
    # Must not confirm the email is already registered.
    assert "already" not in resp.json()["detail"].lower()


def test_session_requires_authentication():
    resp = _client().get("/api/auth/session")
    assert resp.status_code == 401


# --------------------------------------------------------------------------- #
# Association creation & membership
# --------------------------------------------------------------------------- #
def test_creator_becomes_admin(client: TestClient):
    _register(client, "founder@example.com")
    _login(client, "founder@example.com")
    assoc_id = _create_association(client, "Asso One", "one@example.com")

    listed = client.get("/api/auth/associations").json()
    assert listed == [
        {
            "id": assoc_id,
            "name": "Asso One",
            "role": "admin",
            "status": "active",
        }
    ]

    ctx = client.get(f"/api/asso/{assoc_id}")
    assert ctx.status_code == 200
    body = ctx.json()
    assert body["id"] == assoc_id
    assert body["name"] == "Asso One"
    assert body["role"] == "admin"
    # The creator is an admin: effective permissions are the full superset.
    assert set(body["permissions"]) == {p.value for p in Permission}


# --------------------------------------------------------------------------- #
# Tenant isolation (the critical contract)
# --------------------------------------------------------------------------- #
def test_member_of_a_cannot_reach_b():
    alice = _logged_in("alice@example.com")
    bob = _logged_in("bob@example.com")

    assoc_a = _create_association(alice, "Asso A", "a@example.com")
    assoc_b = _create_association(bob, "Asso B", "b@example.com")

    # Each only sees their own.
    assert alice.get(f"/api/asso/{assoc_a}").status_code == 200
    assert bob.get(f"/api/asso/{assoc_b}").status_code == 200

    # Cross access leaks nothing: 404, not 403 (no existence disclosure).
    assert alice.get(f"/api/asso/{assoc_b}").status_code == 404
    assert bob.get(f"/api/asso/{assoc_a}").status_code == 404


def test_unknown_association_is_404():
    alice = _logged_in("alice@example.com")
    assert alice.get("/api/asso/does-not-exist").status_code == 404


def test_unauthenticated_cannot_access_scoped_route():
    assert _client().get("/api/asso/whatever").status_code == 401


def test_legacy_association_token_is_rejected_on_v3_routes():
    """A token minted by the legacy association-login path must not work here."""
    legacy = _client()
    signup = legacy.post(
        "/api/signup",
        json={
            "name": "LegacyAsso",
            "email": "legacy@example.com",
            "password": PASSWORD,
            "balances": [],
        },
    )
    assert signup.status_code == 200, signup.text
    assert (
        legacy.post(
            "/api/login", json={"name": "LegacyAsso", "password": PASSWORD}
        ).status_code
        == 200
    )
    # The legacy access cookie is now set; it must be refused by user-auth.
    assert legacy.get("/api/asso/anything").status_code == 401


# --------------------------------------------------------------------------- #
# RBAC enforcement
# --------------------------------------------------------------------------- #
def test_member_management_requires_permission(client: TestClient, session: Session):
    admin = _logged_in("admin@example.com")
    assoc_id = _create_association(admin, "Asso", "asso@example.com")

    viewer = _client()
    viewer_id = _register(viewer, "viewer@example.com")
    _login(viewer, "viewer@example.com")
    session.add(
        Membership(user_id=viewer_id, association_id=assoc_id, role=Role.VIEWER)
    )
    session.commit()

    # Viewer can see the association context...
    ctx = viewer.get(f"/api/asso/{assoc_id}")
    assert ctx.status_code == 200
    assert ctx.json()["role"] == "viewer"

    # ...but not the admin-only members list.
    assert viewer.get(f"/api/asso/{assoc_id}/members").status_code == 403

    # The admin can.
    members = admin.get(f"/api/asso/{assoc_id}/members")
    assert members.status_code == 200
    emails = {m["email"] for m in members.json()}
    assert emails == {"admin@example.com", "viewer@example.com"}


def test_suspended_membership_is_forbidden(client: TestClient, session: Session):
    admin = _logged_in("admin@example.com")
    assoc_id = _create_association(admin, "Asso", "asso@example.com")

    member = _client()
    member_id = _register(member, "member@example.com")
    _login(member, "member@example.com")
    session.add(
        Membership(
            user_id=member_id,
            association_id=assoc_id,
            role=Role.TREASURER,
            status=MembershipStatus.SUSPENDED,
        )
    )
    session.commit()

    # Suspended -> 403 (distinct from a non-member's 404).
    assert member.get(f"/api/asso/{assoc_id}").status_code == 403
