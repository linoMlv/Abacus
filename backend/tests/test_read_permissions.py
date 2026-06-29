"""Read endpoints enforce the consultation permissions (security).

The dashboard, the journal, the books (balance / grand livre) and every export
must honour ``DASHBOARD_VIEW`` / ``REPORT_VIEW`` — so that revoking a member's
consultation permission actually denies them server-side, not just in the UI.
Built-in roles (viewer and up) hold these by default; an override that removes
them takes effect immediately.
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
    assert (
        client.post(
            "/api/auth/login", json={"email": email, "password": PASSWORD}
        ).status_code
        == 200
    )


def _admin_with_association() -> tuple[TestClient, str]:
    client = _client()
    _register(client, "admin@example.com")
    _login(client, "admin@example.com")
    resp = client.post(
        "/api/auth/associations", json={"name": "Asso", "email": "asso@example.com"}
    )
    assert resp.status_code == 201, resp.text
    return client, resp.json()["id"]


def _viewer(session: Session, assoc_id: str) -> tuple[TestClient, str]:
    client = _client()
    uid = _register(client, "viewer@example.com")
    _login(client, "viewer@example.com")
    session.add(Membership(user_id=uid, association_id=assoc_id, role=Role.VIEWER))
    session.commit()
    return client, uid


def _revoke(admin: TestClient, assoc_id: str, uid: str, permission: Permission) -> None:
    resp = admin.put(
        f"/api/asso/{assoc_id}/members/{uid}/permissions",
        json={"preset_id": None, "overrides": {permission.value: False}},
    )
    assert resp.status_code == 200, resp.text


def _report_paths(assoc_id: str, compte_id: str) -> list[str]:
    base = f"/api/asso/{assoc_id}"
    return [
        f"{base}/ecritures",
        f"{base}/balance",
        f"{base}/comptes/{compte_id}/grand-livre",
        f"{base}/exports/journal.pdf",
        f"{base}/exports/journal.xlsx",
        f"{base}/exports/grand-livre.pdf",
        f"{base}/exports/compte-resultat.pdf",
        f"{base}/exports/bilan.pdf",
    ]


def test_viewer_can_read_dashboard_and_reports_by_default(session: Session):
    admin, assoc_id = _admin_with_association()
    viewer, _ = _viewer(session, assoc_id)
    compte_id = viewer.get(f"/api/asso/{assoc_id}/comptes").json()[0]["id"]

    assert viewer.get(f"/api/asso/{assoc_id}/synthese").status_code == 200
    for path in _report_paths(assoc_id, compte_id):
        assert viewer.get(path).status_code == 200, path


def test_revoking_report_view_denies_books_and_exports(session: Session):
    admin, assoc_id = _admin_with_association()
    viewer, uid = _viewer(session, assoc_id)
    compte_id = viewer.get(f"/api/asso/{assoc_id}/comptes").json()[0]["id"]

    _revoke(admin, assoc_id, uid, Permission.REPORT_VIEW)

    for path in _report_paths(assoc_id, compte_id):
        assert viewer.get(path).status_code == 403, path
    # The dashboard is a separate permission and is unaffected.
    assert viewer.get(f"/api/asso/{assoc_id}/synthese").status_code == 200


def test_revoking_dashboard_view_denies_synthese(session: Session):
    admin, assoc_id = _admin_with_association()
    viewer, uid = _viewer(session, assoc_id)

    _revoke(admin, assoc_id, uid, Permission.DASHBOARD_VIEW)

    assert viewer.get(f"/api/asso/{assoc_id}/synthese").status_code == 403
    # Reports remain readable (distinct permission).
    assert viewer.get(f"/api/asso/{assoc_id}/balance").status_code == 200
