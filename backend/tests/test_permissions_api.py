"""Fine-grained permissions API (T8): per-member overrides + custom presets.

Covers the admin permissions panel surface and, critically, that the overrides
actually move the access boundary end-to-end (``require_permission`` honours the
effective set): a viewer granted ``tresorerie:manage`` can create a treasury
account; a treasurer revoked it is denied. Every endpoint is guarded by
``MEMBER_MANAGE`` and tenant-scoped (cross-association access is ``404``).
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from authz import Permission
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


def _admin_with_association(email: str, name: str = "Asso") -> tuple[TestClient, str]:
    client = _client()
    _register(client, email)
    _login(client, email)
    resp = client.post(
        "/api/auth/associations", json={"name": name, "email": f"{name}@example.com"}
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


# --------------------------------------------------------------------------- #
# Catalog
# --------------------------------------------------------------------------- #
def test_catalog_lists_every_permission(session: Session):
    admin, assoc_id = _admin_with_association("admin@example.com")
    resp = admin.get(f"/api/asso/{assoc_id}/permissions/catalog")
    assert resp.status_code == 200, resp.text
    values = {item["value"] for item in resp.json()}
    assert values == {p.value for p in Permission}
    assert all(item["group"] and item["label"] for item in resp.json())


def test_catalog_requires_member_manage(session: Session):
    _admin, assoc_id = _admin_with_association("admin@example.com")
    treasurer, _ = _add_member(
        session, assoc_id, "treasurer@example.com", Role.TREASURER
    )
    assert (
        treasurer.get(f"/api/asso/{assoc_id}/permissions/catalog").status_code == 403
    )


# --------------------------------------------------------------------------- #
# Reading a member's permissions
# --------------------------------------------------------------------------- #
def test_admin_reads_a_member_permissions(session: Session):
    admin, assoc_id = _admin_with_association("admin@example.com")
    _, viewer_id = _add_member(session, assoc_id, "viewer@example.com", Role.VIEWER)

    resp = admin.get(f"/api/asso/{assoc_id}/members/{viewer_id}/permissions")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["role"] == "viewer"
    assert body["is_admin"] is False
    assert body["preset_id"] is None
    assert body["overrides"] == {}
    assert set(body["effective"]) == {
        Permission.DASHBOARD_VIEW.value,
        Permission.REPORT_VIEW.value,
    }


def test_admin_member_permissions_are_full_and_immutable(session: Session):
    admin, assoc_id = _admin_with_association("admin@example.com")
    _, other_admin_id = _add_member(session, assoc_id, "admin2@example.com", Role.ADMIN)

    read = admin.get(f"/api/asso/{assoc_id}/members/{other_admin_id}/permissions")
    assert read.status_code == 200
    body = read.json()
    assert body["is_admin"] is True
    assert set(body["effective"]) == {p.value for p in Permission}

    # An admin cannot be restricted: editing their permissions is rejected.
    resp = admin.put(
        f"/api/asso/{assoc_id}/members/{other_admin_id}/permissions",
        json={"overrides": {Permission.MEMBER_MANAGE.value: False}},
    )
    assert resp.status_code == 400


# --------------------------------------------------------------------------- #
# Overrides actually move the access boundary (end-to-end)
# --------------------------------------------------------------------------- #
def test_grant_override_lets_a_viewer_manage_treasury(session: Session):
    admin, assoc_id = _admin_with_association("admin@example.com")
    viewer, viewer_id = _add_member(
        session, assoc_id, "viewer@example.com", Role.VIEWER
    )

    # Before: a viewer cannot create a treasury account.
    payload = {"nom": "Caisse", "type_tresorerie": "caisse"}
    assert (
        viewer.post(f"/api/asso/{assoc_id}/tresorerie", json=payload).status_code == 403
    )

    grant = admin.put(
        f"/api/asso/{assoc_id}/members/{viewer_id}/permissions",
        json={"overrides": {Permission.TRESORERIE_MANAGE.value: True}},
    )
    assert grant.status_code == 200, grant.text
    assert Permission.TRESORERIE_MANAGE.value in grant.json()["effective"]

    # After: the same viewer may now create one.
    assert (
        viewer.post(f"/api/asso/{assoc_id}/tresorerie", json=payload).status_code == 201
    )


def test_revoke_override_strips_a_treasurer_capability(session: Session):
    admin, assoc_id = _admin_with_association("admin@example.com")
    treasurer, treasurer_id = _add_member(
        session, assoc_id, "treasurer@example.com", Role.TREASURER
    )

    payload = {"nom": "Caisse", "type_tresorerie": "caisse"}
    assert (
        treasurer.post(f"/api/asso/{assoc_id}/tresorerie", json=payload).status_code
        == 201
    )

    revoke = admin.put(
        f"/api/asso/{assoc_id}/members/{treasurer_id}/permissions",
        json={"overrides": {Permission.TRESORERIE_MANAGE.value: False}},
    )
    assert revoke.status_code == 200, revoke.text
    assert Permission.TRESORERIE_MANAGE.value not in revoke.json()["effective"]

    assert (
        treasurer.post(f"/api/asso/{assoc_id}/tresorerie", json=payload).status_code
        == 403
    )


def test_unknown_permission_key_is_rejected(session: Session):
    admin, assoc_id = _admin_with_association("admin@example.com")
    _, viewer_id = _add_member(session, assoc_id, "viewer@example.com", Role.VIEWER)
    resp = admin.put(
        f"/api/asso/{assoc_id}/members/{viewer_id}/permissions",
        json={"overrides": {"not:a:permission": True}},
    )
    assert resp.status_code == 422


# --------------------------------------------------------------------------- #
# Custom presets (reusable named permission sets)
# --------------------------------------------------------------------------- #
def test_preset_lifecycle_and_assignment(session: Session):
    admin, assoc_id = _admin_with_association("admin@example.com")
    viewer, viewer_id = _add_member(
        session, assoc_id, "viewer@example.com", Role.VIEWER
    )

    perms = [Permission.DASHBOARD_VIEW.value, Permission.EVENT_MANAGE.value]
    created = admin.post(
        f"/api/asso/{assoc_id}/permission-presets",
        json={"nom": "Équipe Gala", "permissions": perms},
    )
    assert created.status_code == 201, created.text
    preset_id = created.json()["id"]
    assert set(created.json()["permissions"]) == set(perms)

    listed = admin.get(f"/api/asso/{assoc_id}/permission-presets")
    assert listed.status_code == 200
    assert any(p["id"] == preset_id for p in listed.json())

    # Assign the preset to the viewer: its base now replaces the role's.
    assign = admin.put(
        f"/api/asso/{assoc_id}/members/{viewer_id}/permissions",
        json={"preset_id": preset_id, "overrides": {}},
    )
    assert assign.status_code == 200, assign.text
    assert set(assign.json()["effective"]) == set(perms)

    # The viewer may now manage events (a preset grant), end-to-end.
    ev = viewer.post(
        f"/api/asso/{assoc_id}/evenements", json={"nom": "Gala 2026"}
    )
    assert ev.status_code == 201, ev.text

    # Deleting the preset detaches it; the member falls back to the role base.
    delete = admin.delete(f"/api/asso/{assoc_id}/permission-presets/{preset_id}")
    assert delete.status_code == 200, delete.text
    after = admin.get(f"/api/asso/{assoc_id}/members/{viewer_id}/permissions")
    assert after.json()["preset_id"] is None
    assert set(after.json()["effective"]) == {
        Permission.DASHBOARD_VIEW.value,
        Permission.REPORT_VIEW.value,
    }


def test_preset_name_unique_per_association(session: Session):
    admin, assoc_id = _admin_with_association("admin@example.com")
    body = {"nom": "Bénévole", "permissions": [Permission.DASHBOARD_VIEW.value]}
    assert (
        admin.post(f"/api/asso/{assoc_id}/permission-presets", json=body).status_code
        == 201
    )
    assert (
        admin.post(f"/api/asso/{assoc_id}/permission-presets", json=body).status_code
        == 400
    )


def test_preset_rejects_unknown_permission(session: Session):
    admin, assoc_id = _admin_with_association("admin@example.com")
    resp = admin.post(
        f"/api/asso/{assoc_id}/permission-presets",
        json={"nom": "Bad", "permissions": ["nope:nope"]},
    )
    assert resp.status_code == 422


def test_assigning_a_foreign_preset_is_404(session: Session):
    admin_a, assoc_a = _admin_with_association("admina@example.com", name="AssoA")
    _, viewer_id = _add_member(session, assoc_a, "viewer@example.com", Role.VIEWER)

    admin_b, assoc_b = _admin_with_association("adminb@example.com", name="AssoB")
    foreign = admin_b.post(
        f"/api/asso/{assoc_b}/permission-presets",
        json={"nom": "B", "permissions": [Permission.DASHBOARD_VIEW.value]},
    ).json()["id"]

    resp = admin_a.put(
        f"/api/asso/{assoc_a}/members/{viewer_id}/permissions",
        json={"preset_id": foreign, "overrides": {}},
    )
    assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# RBAC + isolation
# --------------------------------------------------------------------------- #
def test_non_admin_cannot_use_permissions_api(session: Session):
    _admin, assoc_id = _admin_with_association("admin@example.com")
    treasurer, _ = _add_member(
        session, assoc_id, "treasurer@example.com", Role.TREASURER
    )
    _, viewer_id = _add_member(session, assoc_id, "viewer@example.com", Role.VIEWER)

    assert (
        treasurer.get(
            f"/api/asso/{assoc_id}/members/{viewer_id}/permissions"
        ).status_code
        == 403
    )
    assert (
        treasurer.put(
            f"/api/asso/{assoc_id}/members/{viewer_id}/permissions",
            json={"overrides": {Permission.EVENT_MANAGE.value: True}},
        ).status_code
        == 403
    )
    assert (
        treasurer.get(f"/api/asso/{assoc_id}/permission-presets").status_code == 403
    )


def test_cannot_touch_another_association_member_permissions(session: Session):
    admin_a, assoc_a = _admin_with_association("admina@example.com", name="AssoA")
    admin_b, assoc_b = _admin_with_association("adminb@example.com", name="AssoB")
    _, victim_id = _add_member(session, assoc_b, "victim@example.com", Role.VIEWER)

    # Admin of A, using B's path for a member of B, gets 404 (no member in A).
    assert (
        admin_a.get(
            f"/api/asso/{assoc_b}/members/{victim_id}/permissions"
        ).status_code
        == 404
    )
    assert (
        admin_a.put(
            f"/api/asso/{assoc_b}/members/{victim_id}/permissions",
            json={"overrides": {Permission.EVENT_MANAGE.value: True}},
        ).status_code
        == 404
    )
