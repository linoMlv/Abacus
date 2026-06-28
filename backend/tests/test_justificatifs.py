"""Supporting documents (justificatifs) on entries — T3c.

Security-first file upload: the stored content type is determined from the
file's *magic bytes*, never trusted from the client; only PDF and common raster
images are accepted (no SVG/HTML — XSS); size is capped; storage keys are
server-generated (no path traversal); downloads are tenant-scoped and forced as
attachments. Storage goes through a ``FileStorage`` abstraction (local here,
S3/MinIO later).
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from database import get_session
from file_storage import LocalFileStorage, get_storage
from main import _fastapi_app as app
from models import Membership, Role

PASSWORD = "password123"
TODAY = "2026-06-27"

PDF_BYTES = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
HTML_DISGUISED_AS_PNG = b"<html><script>alert(document.cookie)</script></html>"
SVG_BYTES = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'


@pytest.fixture(autouse=True)
def _overrides(session: Session, tmp_path):
    app.dependency_overrides[get_session] = lambda: session
    storage = LocalFileStorage(tmp_path)
    app.dependency_overrides[get_storage] = lambda: storage
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


def _entry(client: TestClient, assoc: str) -> str:
    cat = next(
        c
        for c in client.get(f"/api/asso/{assoc}/categories").json()
        if c["libelle"] == "Cotisations"
    )
    banque = next(
        c
        for c in client.get(f"/api/asso/{assoc}/tresorerie").json()
        if c["numero"] == "512"
    )
    resp = client.post(
        f"/api/asso/{assoc}/ecritures/simple",
        json={
            "categorie_id": cat["id"],
            "compte_tresorerie_id": banque["id"],
            "montant": "10.00",
            "date": TODAY,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _upload(client, assoc, entry, name, content, content_type):
    return client.post(
        f"/api/asso/{assoc}/ecritures/{entry}/justificatifs",
        files={"file": (name, content, content_type)},
    )


# --- Happy path -----------------------------------------------------------


def test_upload_pdf_then_list_and_download():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    entry = _entry(admin, assoc)

    up = _upload(admin, assoc, entry, "facture.pdf", PDF_BYTES, "application/pdf")
    assert up.status_code == 201, up.text
    body = up.json()
    assert body["filename"] == "facture.pdf"
    assert body["content_type"] == "application/pdf"
    assert body["size"] == len(PDF_BYTES)

    listed = admin.get(f"/api/asso/{assoc}/ecritures/{entry}/justificatifs").json()
    assert [j["id"] for j in listed] == [body["id"]]

    dl = admin.get(f"/api/asso/{assoc}/justificatifs/{body['id']}/contenu")
    assert dl.status_code == 200
    assert dl.content == PDF_BYTES
    assert dl.headers["content-type"].startswith("application/pdf")
    # Forced download + no MIME sniffing (defense against active content).
    assert "attachment" in dl.headers["content-disposition"]
    assert dl.headers["x-content-type-options"] == "nosniff"


def test_upload_png_is_accepted():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    entry = _entry(admin, assoc)
    up = _upload(admin, assoc, entry, "recu.png", PNG_BYTES, "image/png")
    assert up.status_code == 201, up.text
    assert up.json()["content_type"] == "image/png"


def test_preview_serves_inline_sandboxed():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    entry = _entry(admin, assoc)
    jid = _upload(
        admin, assoc, entry, "facture.pdf", PDF_BYTES, "application/pdf"
    ).json()["id"]

    ap = admin.get(f"/api/asso/{assoc}/justificatifs/{jid}/apercu")
    assert ap.status_code == 200
    assert ap.content == PDF_BYTES
    assert ap.headers["content-type"].startswith("application/pdf")
    # Rendered in-app, but sandboxed and non-sniffable.
    assert "inline" in ap.headers["content-disposition"]
    assert ap.headers["x-content-type-options"] == "nosniff"
    assert ap.headers["content-security-policy"] == "sandbox"
    # Same-origin framing allowed (so the PDF iframe renders), cross-origin denied.
    assert ap.headers["x-frame-options"] == "SAMEORIGIN"


def test_preview_is_tenant_scoped():
    admin_a, assoc_a = _admin_with_association("a@example.com", "alpha")
    admin_b, assoc_b = _admin_with_association("b@example.com", "beta")
    entry_a = _entry(admin_a, assoc_a)
    jid = _upload(
        admin_a, assoc_a, entry_a, "f.pdf", PDF_BYTES, "application/pdf"
    ).json()["id"]
    assert (
        admin_b.get(f"/api/asso/{assoc_b}/justificatifs/{jid}/apercu").status_code
        == 404
    )


# --- Security: content sniffing & limits ----------------------------------


def test_rejects_html_disguised_as_png():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    entry = _entry(admin, assoc)
    up = _upload(admin, assoc, entry, "evil.png", HTML_DISGUISED_AS_PNG, "image/png")
    assert up.status_code == 400, up.text


def test_rejects_svg():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    entry = _entry(admin, assoc)
    up = _upload(admin, assoc, entry, "x.svg", SVG_BYTES, "image/svg+xml")
    assert up.status_code == 400, up.text


def test_rejects_oversize_file():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    entry = _entry(admin, assoc)
    big = PDF_BYTES + b"\x00" * (5 * 1024 * 1024 + 1)
    up = _upload(admin, assoc, entry, "big.pdf", big, "application/pdf")
    assert up.status_code == 413, up.text


def test_rejects_empty_file():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    entry = _entry(admin, assoc)
    up = _upload(admin, assoc, entry, "empty.pdf", b"", "application/pdf")
    assert up.status_code == 400, up.text


# --- RBAC & tenant isolation ----------------------------------------------


def test_upload_requires_attachment_permission(session: Session):
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    entry = _entry(admin, assoc)
    viewer = _member_client(session, assoc, "v@example.com", Role.VIEWER)
    up = _upload(viewer, assoc, entry, "f.pdf", PDF_BYTES, "application/pdf")
    assert up.status_code == 403, up.text


def test_upload_to_cross_tenant_entry_is_404():
    admin_a, assoc_a = _admin_with_association("a@example.com", "alpha")
    admin_b, assoc_b = _admin_with_association("b@example.com", "beta")
    entry_b = _entry(admin_b, assoc_b)
    up = _upload(admin_a, assoc_a, entry_b, "f.pdf", PDF_BYTES, "application/pdf")
    assert up.status_code == 404, up.text


def test_download_is_tenant_scoped():
    admin_a, assoc_a = _admin_with_association("a@example.com", "alpha")
    admin_b, assoc_b = _admin_with_association("b@example.com", "beta")
    entry_a = _entry(admin_a, assoc_a)
    jid = _upload(
        admin_a, assoc_a, entry_a, "f.pdf", PDF_BYTES, "application/pdf"
    ).json()["id"]

    # B cannot read A's justificatif through B's own scope.
    assert (
        admin_b.get(f"/api/asso/{assoc_b}/justificatifs/{jid}/contenu").status_code
        == 404
    )
    # …nor through A's path (not a member of A).
    assert (
        admin_b.get(f"/api/asso/{assoc_a}/justificatifs/{jid}/contenu").status_code
        == 404
    )


def test_a_viewer_can_read_but_not_delete():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    entry = _entry(admin, assoc)
    jid = _upload(admin, assoc, entry, "f.pdf", PDF_BYTES, "application/pdf").json()[
        "id"
    ]
    session = app.dependency_overrides[get_session]()
    viewer = _member_client(session, assoc, "v@example.com", Role.VIEWER)

    assert (
        viewer.get(f"/api/asso/{assoc}/justificatifs/{jid}/contenu").status_code == 200
    )
    assert viewer.delete(f"/api/asso/{assoc}/justificatifs/{jid}").status_code == 403


def test_delete_removes_the_justificatif():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    entry = _entry(admin, assoc)
    jid = _upload(admin, assoc, entry, "f.pdf", PDF_BYTES, "application/pdf").json()[
        "id"
    ]

    assert admin.delete(f"/api/asso/{assoc}/justificatifs/{jid}").status_code == 204
    assert (
        admin.get(f"/api/asso/{assoc}/justificatifs/{jid}/contenu").status_code == 404
    )
    assert admin.get(f"/api/asso/{assoc}/ecritures/{entry}/justificatifs").json() == []
