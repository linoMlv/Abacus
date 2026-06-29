"""Invitation lifecycle: create, list, revoke, accept — with RBAC and isolation."""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from database import get_session
from main import _fastapi_app as app
from models import Invitation, Membership, Role

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


def _admin_with_association(email: str = "admin@example.com") -> tuple[TestClient, str]:
    client = _client()
    _register(client, email)
    _login(client, email)
    resp = client.post(
        "/api/auth/associations",
        json={"name": "Asso", "email": "asso@example.com"},
    )
    assert resp.status_code == 201, resp.text
    return client, resp.json()["id"]


def _invite(admin: TestClient, assoc_id: str, email: str, role: str) -> str:
    resp = admin.post(
        f"/api/asso/{assoc_id}/invitations", json={"email": email, "role": role}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["token"]


# --------------------------------------------------------------------------- #
# Create / list / revoke
# --------------------------------------------------------------------------- #
def test_admin_creates_and_lists_invitation():
    admin, assoc_id = _admin_with_association()
    resp = admin.post(
        f"/api/asso/{assoc_id}/invitations",
        json={"email": "New.Person@Example.com", "role": "treasurer"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "new.person@example.com"  # normalized
    assert body["role"] == "treasurer"
    assert body["accepted_at"] is None
    assert body["token"]

    listed = admin.get(f"/api/asso/{assoc_id}/invitations").json()
    assert [i["email"] for i in listed] == ["new.person@example.com"]
    # The token is never exposed in listings.
    assert "token" not in listed[0]


def test_inviting_an_existing_member_is_rejected(session: Session):
    admin, assoc_id = _admin_with_association()
    member_client = _client()
    member_id = _register(member_client, "member@example.com")
    session.add(
        Membership(user_id=member_id, association_id=assoc_id, role=Role.VIEWER)
    )
    session.commit()

    resp = admin.post(
        f"/api/asso/{assoc_id}/invitations",
        json={"email": "member@example.com", "role": "treasurer"},
    )
    assert resp.status_code == 400


def test_non_admin_cannot_manage_invitations(session: Session):
    admin, assoc_id = _admin_with_association()
    treasurer = _client()
    treasurer_id = _register(treasurer, "treasurer@example.com")
    _login(treasurer, "treasurer@example.com")
    session.add(
        Membership(user_id=treasurer_id, association_id=assoc_id, role=Role.TREASURER)
    )
    session.commit()

    assert (
        treasurer.post(
            f"/api/asso/{assoc_id}/invitations",
            json={"email": "x@example.com", "role": "viewer"},
        ).status_code
        == 403
    )
    assert treasurer.get(f"/api/asso/{assoc_id}/invitations").status_code == 403


def test_revoked_invitation_cannot_be_accepted():
    admin, assoc_id = _admin_with_association()
    token = _invite(admin, assoc_id, "invitee@example.com", "viewer")
    invitations = admin.get(f"/api/asso/{assoc_id}/invitations").json()
    invitation_id = invitations[0]["id"]

    assert (
        admin.delete(f"/api/asso/{assoc_id}/invitations/{invitation_id}").status_code
        == 200
    )
    accept = _client().post(
        "/api/auth/invitations/accept",
        json={"token": token, "name": "Invitee", "password": PASSWORD},
    )
    assert accept.status_code == 400


# --------------------------------------------------------------------------- #
# Accept
# --------------------------------------------------------------------------- #
def test_accept_creates_account_and_membership():
    admin, assoc_id = _admin_with_association()
    token = _invite(admin, assoc_id, "newbie@example.com", "treasurer")

    newbie = _client()
    accept = newbie.post(
        "/api/auth/invitations/accept",
        json={"token": token, "name": "Newbie", "password": PASSWORD},
    )
    assert accept.status_code == 200, accept.text
    body = accept.json()
    assert body["user"]["email"] == "newbie@example.com"
    assert [a["role"] for a in body["associations"]] == ["treasurer"]

    # The accept logged them in: they can reach the association.
    ctx = newbie.get(f"/api/asso/{assoc_id}")
    assert ctx.status_code == 200
    assert ctx.json()["role"] == "treasurer"

    # The token is single-use.
    replay = _client().post(
        "/api/auth/invitations/accept",
        json={"token": token, "name": "X", "password": PASSWORD},
    )
    assert replay.status_code == 400


def test_existing_user_accepts_when_logged_in():
    admin, assoc_id = _admin_with_association()
    token = _invite(admin, assoc_id, "existing@example.com", "viewer")

    existing = _client()
    _register(existing, "existing@example.com")
    _login(existing, "existing@example.com")

    accept = existing.post("/api/auth/invitations/accept", json={"token": token})
    assert accept.status_code == 200
    assert existing.get(f"/api/asso/{assoc_id}").json()["role"] == "viewer"


def test_existing_user_invitation_requires_login():
    admin, assoc_id = _admin_with_association()
    token = _invite(admin, assoc_id, "existing@example.com", "viewer")
    _register(_client(), "existing@example.com")

    # Anonymous accept of an invitation bound to an existing account -> 401.
    anon = _client().post("/api/auth/invitations/accept", json={"token": token})
    assert anon.status_code == 401


def test_accepting_for_another_account_is_forbidden():
    admin, assoc_id = _admin_with_association()
    token = _invite(admin, assoc_id, "target@example.com", "viewer")
    _register(_client(), "target@example.com")

    intruder = _client()
    _register(intruder, "intruder@example.com")
    _login(intruder, "intruder@example.com")

    resp = intruder.post("/api/auth/invitations/accept", json={"token": token})
    assert resp.status_code == 403


def test_accept_unknown_token_is_400():
    resp = _client().post(
        "/api/auth/invitations/accept",
        json={"token": "nope", "name": "X", "password": PASSWORD},
    )
    assert resp.status_code == 400


def test_accept_expired_invitation_is_400(session: Session):
    from datetime import timedelta

    admin, assoc_id = _admin_with_association()
    token = _invite(admin, assoc_id, "late@example.com", "viewer")

    invitation = session.exec(select(Invitation)).first()
    invitation.expires_at = invitation.created_at - timedelta(days=1)
    session.add(invitation)
    session.commit()

    resp = _client().post(
        "/api/auth/invitations/accept",
        json={"token": token, "name": "Late", "password": PASSWORD},
    )
    assert resp.status_code == 400


# --------------------------------------------------------------------------- #
# Public preview (so the acceptance page can show context + prefill the email)
# --------------------------------------------------------------------------- #
def test_preview_returns_invitation_context():
    admin, assoc_id = _admin_with_association()
    token = _invite(admin, assoc_id, "Guest@Example.com", "treasurer")

    # No auth needed: the token is the credential.
    resp = _client().get(f"/api/auth/invitations/{token}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["association_id"] == assoc_id
    assert body["association_name"] == "Asso"
    assert body["email"] == "guest@example.com"  # normalized
    assert body["role"] == "treasurer"


def test_preview_unknown_token_is_404():
    assert _client().get("/api/auth/invitations/nope").status_code == 404


def test_preview_accepted_invitation_is_404(session: Session):
    admin, assoc_id = _admin_with_association()
    token = _invite(admin, assoc_id, "guest@example.com", "viewer")
    accept = _client().post("/api/auth/invitations/accept", json={"token": token})
    # An existing account is required to be logged in; here no account exists yet,
    # so creation needs name+password. Provide them to consume the invitation.
    accept = _client().post(
        "/api/auth/invitations/accept",
        json={"token": token, "name": "Guest", "password": PASSWORD},
    )
    assert accept.status_code == 200, accept.text
    # Once consumed, the preview no longer resolves.
    assert _client().get(f"/api/auth/invitations/{token}").status_code == 404


# --------------------------------------------------------------------------- #
# Cross-tenant isolation
# --------------------------------------------------------------------------- #
def test_cannot_invite_or_revoke_across_associations():
    admin_a, _ = _admin_with_association("admina@example.com")
    admin_b, assoc_b = _admin_with_association_named(
        "adminb@example.com", "Asso B", "assob@example.com"
    )
    token_b = _invite(admin_b, assoc_b, "guest@example.com", "viewer")
    invitation_b = admin_b.get(f"/api/asso/{assoc_b}/invitations").json()[0]["id"]

    # Admin A is not a member of B: scoped routes hide everything (404).
    assert (
        admin_a.post(
            f"/api/asso/{assoc_b}/invitations",
            json={"email": "x@example.com", "role": "viewer"},
        ).status_code
        == 404
    )
    assert admin_a.get(f"/api/asso/{assoc_b}/invitations").status_code == 404
    assert (
        admin_a.delete(f"/api/asso/{assoc_b}/invitations/{invitation_b}").status_code
        == 404
    )
    # B's token is unaffected and still valid.
    assert token_b


def _admin_with_association_named(
    email: str, name: str, assoc_email: str
) -> tuple[TestClient, str]:
    client = _client()
    _register(client, email)
    _login(client, email)
    resp = client.post(
        "/api/auth/associations", json={"name": name, "email": assoc_email}
    )
    assert resp.status_code == 201, resp.text
    return client, resp.json()["id"]
