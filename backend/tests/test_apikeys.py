"""API keys (machine credentials for MCP v2, Phase 6).

A key is bound to a ``Membership``: it acts as that member and inherits their
*effective* permissions live (role/preset ± overrides). Creation/listing/
revocation is gated by ``APIKEY_MANAGE`` (admin). The raw key is shown once at
creation and stored only as a hash. The resolver rejects revoked keys, keys of
a suspended/removed member, and never leaks another tenant's keys.
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from api_auth import resolve_api_key
from database import get_session
from main import _fastapi_app as app
from models import ApiKey, Membership, MembershipStatus, Role, User

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
        "/api/auth/associations",
        json={"name": name, "email": f"{name}@example.com"},
    )
    assert resp.status_code == 201, resp.text
    return client, resp.json()["id"]


def _add_member(session: Session, assoc_id: str, email: str, role: Role) -> str:
    """Insert a second member directly (bypasses the invitation flow)."""
    from security import get_password_hash

    user = User(email=email, password=get_password_hash(PASSWORD), name=email)
    session.add(user)
    session.flush()
    session.add(Membership(user_id=user.id, association_id=assoc_id, role=role))
    session.commit()
    return user.id


# --- CRUD & RBAC ---------------------------------------------------------


def test_create_key_returns_raw_once_then_only_hash_stored(session: Session):
    client, assoc = _admin_with_association("admin@a.com", "Alpha")

    resp = client.post(f"/api/asso/{assoc}/api-keys", json={"name": "MCP Claude"})
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["name"] == "MCP Claude"
    raw = body["key"]
    assert raw.startswith("abk_")
    assert body["prefix"] and body["prefix"] in raw

    # The raw key is never returned again by the listing.
    listed = client.get(f"/api/asso/{assoc}/api-keys").json()
    assert len(listed) == 1
    assert "key" not in listed[0]
    assert listed[0]["prefix"] == body["prefix"]

    # Only a hash is persisted.
    key = session.get(ApiKey, body["id"])
    assert key is not None
    assert key.key_hash != raw
    assert raw not in key.key_hash


def test_non_admin_cannot_manage_keys(session: Session):
    client, assoc = _admin_with_association("admin2@a.com", "Beta")
    _add_member(session, assoc, "tres@a.com", Role.TREASURER)

    tres = _client()
    _login(tres, "tres@a.com")
    assert (
        tres.post(f"/api/asso/{assoc}/api-keys", json={"name": "x"}).status_code == 403
    )
    assert tres.get(f"/api/asso/{assoc}/api-keys").status_code == 403


def test_key_bound_to_chosen_member_inherits_that_role(session: Session):
    client, assoc = _admin_with_association("admin3@a.com", "Gamma")
    viewer_id = _add_member(session, assoc, "viewer@a.com", Role.VIEWER)

    resp = client.post(
        f"/api/asso/{assoc}/api-keys",
        json={"name": "read-only", "user_id": viewer_id},
    )
    assert resp.status_code == 201, resp.text
    raw = resp.json()["key"]

    ctx = resolve_api_key(session, raw)
    assert ctx is not None
    assert ctx.role == Role.VIEWER
    from authz import Permission

    assert Permission.DASHBOARD_VIEW in ctx.permissions
    assert Permission.ENTRY_CREATE_SIMPLE not in ctx.permissions


def test_cannot_bind_key_to_foreign_member(session: Session):
    client_a, assoc_a = _admin_with_association("a@x.com", "AX")
    _, assoc_b = _admin_with_association("b@x.com", "BX")
    foreign = _add_member(session, assoc_b, "m@bx.com", Role.TREASURER)

    # A user id that has no membership in tenant A resolves to 404 (no binding).
    resp = client_a.post(
        f"/api/asso/{assoc_a}/api-keys",
        json={"name": "x", "user_id": foreign},
    )
    assert resp.status_code == 404


# --- Resolver security ---------------------------------------------------


def test_resolver_rejects_revoked_key(session: Session):
    client, assoc = _admin_with_association("admin4@a.com", "Delta")
    created = client.post(f"/api/asso/{assoc}/api-keys", json={"name": "k"}).json()
    raw = created["key"]

    assert resolve_api_key(session, raw) is not None

    assert (
        client.delete(f"/api/asso/{assoc}/api-keys/{created['id']}").status_code == 204
    )
    assert resolve_api_key(session, raw) is None


def test_resolver_rejects_key_of_suspended_member(session: Session):
    client, assoc = _admin_with_association("admin5@a.com", "Eps")
    viewer_id = _add_member(session, assoc, "v2@a.com", Role.VIEWER)
    created = client.post(
        f"/api/asso/{assoc}/api-keys",
        json={"name": "k", "user_id": viewer_id},
    ).json()

    assert resolve_api_key(session, created["key"]) is not None

    m = session.exec(
        Membership.__table__.select().where(Membership.user_id == viewer_id)
    ).first()
    m = session.get(Membership, m.id)
    m.status = MembershipStatus.SUSPENDED
    session.add(m)
    session.commit()
    assert resolve_api_key(session, created["key"]) is None


def test_resolver_rejects_garbage(session: Session):
    assert resolve_api_key(session, "not-a-key") is None
    assert resolve_api_key(session, "abk_deadbeef") is None
    assert resolve_api_key(session, "") is None


def test_resolver_updates_last_used(session: Session):
    client, assoc = _admin_with_association("admin6@a.com", "Zeta")
    created = client.post(f"/api/asso/{assoc}/api-keys", json={"name": "k"}).json()

    assert session.get(ApiKey, created["id"]).last_used_at is None
    resolve_api_key(session, created["key"])
    session.expire_all()
    assert session.get(ApiKey, created["id"]).last_used_at is not None


def test_keys_isolated_between_tenants(session: Session):
    client_a, assoc_a = _admin_with_association("iso_a@a.com", "IsoA")
    client_b, assoc_b = _admin_with_association("iso_b@a.com", "IsoB")
    client_a.post(f"/api/asso/{assoc_a}/api-keys", json={"name": "ka"})

    # B's admin sees none of A's keys, and cannot list A's tenant (404: non-member).
    assert client_b.get(f"/api/asso/{assoc_b}/api-keys").json() == []
    assert client_b.get(f"/api/asso/{assoc_a}/api-keys").status_code == 404
