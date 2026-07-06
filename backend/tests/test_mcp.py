"""MCP v2 tool dispatch: permission-filtered advertising, server-side re-check,
assisted writes that stay brouillon, and the read/write guardrails (plan §7).

The dispatch core (``run_tool`` / ``available_tools_for_key``) is exercised
directly with a raw key — no HTTP transport needed. MCP calls open their own
session, so we bind ``mcp_server.session`` to the test engine.
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

import mcp_server.session as mcp_session
from database import get_session
from main import _fastapi_app as app
from mcp_server.dispatch import (
    ToolAuthError,
    ToolError,
    available_tools_for_key,
    run_tool,
)
from models import Ecriture, EcritureStatut, Membership, Role, User

PASSWORD = "password123"


@pytest.fixture(autouse=True)
def _wire(session: Session, monkeypatch):
    app.dependency_overrides[get_session] = lambda: session
    # MCP tool calls open their own session; bind them to the test engine so they
    # see data the API committed on the shared in-memory connection.
    monkeypatch.setattr(mcp_session, "engine", session.get_bind())
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
    from security import get_password_hash

    user = User(email=email, password=get_password_hash(PASSWORD), name=email)
    session.add(user)
    session.flush()
    m = Membership(user_id=user.id, association_id=assoc_id, role=role)
    session.add(m)
    session.commit()
    return user.id


def _key_for_member(client: TestClient, assoc: str, user_id: str | None = None) -> str:
    body = {"name": "k"}
    if user_id is not None:
        body["user_id"] = user_id
    resp = client.post(f"/api/asso/{assoc}/api-keys", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()["key"]


def _recette_category(client: TestClient, assoc: str) -> None:
    resp = client.post(
        f"/api/asso/{assoc}/categories",
        json={"sens": "recette", "libelle": "MCP Recette"},
    )
    assert resp.status_code in (200, 201), resp.text


# --- Tool advertising is permission-filtered -----------------------------


def test_viewer_key_sees_only_read_tools(session: Session):
    client, assoc = _admin_with_association("adm@a.com", "A1")
    viewer_uid = _add_member(session, assoc, "view@a.com", Role.VIEWER)
    key = _key_for_member(client, assoc, viewer_uid)

    names = {spec.name for spec in available_tools_for_key(key)}
    assert "get_synthese" in names
    assert "balance_comptes" in names
    # No write tools, no donation tool for a viewer.
    assert "saisir_recette" not in names
    assert "saisir_depense" not in names
    assert "creer_tiers" not in names
    assert "list_dons" not in names


def test_treasurer_key_sees_write_tools(session: Session):
    client, assoc = _admin_with_association("adm2@a.com", "A2")
    tres_uid = _add_member(session, assoc, "tres@a.com", Role.TREASURER)
    key = _key_for_member(client, assoc, tres_uid)

    names = {spec.name for spec in available_tools_for_key(key)}
    assert {"saisir_recette", "saisir_depense", "creer_tiers", "list_dons"} <= names


def test_invalid_key_advertises_nothing(session: Session):
    assert available_tools_for_key("abk_nope") == []


# --- Server-side re-check on execution -----------------------------------


def test_read_tool_runs_for_viewer(session: Session):
    client, assoc = _admin_with_association("adm3@a.com", "A3")
    viewer_uid = _add_member(session, assoc, "v3@a.com", Role.VIEWER)
    key = _key_for_member(client, assoc, viewer_uid)

    out = run_tool(key, "get_synthese", {})
    assert '"resultat"' in out


def test_forbidden_write_tool_rejected_even_if_called(session: Session):
    client, assoc = _admin_with_association("adm4@a.com", "A4")
    viewer_uid = _add_member(session, assoc, "v4@a.com", Role.VIEWER)
    key = _key_for_member(client, assoc, viewer_uid)

    with pytest.raises(ToolError):
        run_tool(
            key,
            "saisir_recette",
            {"montant": 10, "categorie": "x", "compte_tresorerie": "Banque"},
        )


def test_invalid_key_execution_raises_auth(session: Session):
    with pytest.raises(ToolAuthError):
        run_tool("abk_bad", "get_synthese", {})


def test_revoked_key_cannot_run(session: Session):
    client, assoc = _admin_with_association("adm5@a.com", "A5")
    created = client.post(f"/api/asso/{assoc}/api-keys", json={"name": "k"}).json()
    key = created["key"]
    assert run_tool(key, "get_synthese", {})  # works while active
    assert (
        client.delete(f"/api/asso/{assoc}/api-keys/{created['id']}").status_code == 204
    )
    with pytest.raises(ToolAuthError):
        run_tool(key, "get_synthese", {})


# --- Assisted write always creates a brouillon ---------------------------


def test_saisir_recette_creates_brouillon(session: Session):
    client, assoc = _admin_with_association("adm6@a.com", "A6")
    _recette_category(client, assoc)
    # Admin's own key holds ENTRY_CREATE_SIMPLE.
    key = _key_for_member(client, assoc)

    out = run_tool(
        key,
        "saisir_recette",
        {"montant": 150, "categorie": "MCP Recette", "compte_tresorerie": "Banque"},
    )
    assert "brouillon_cree" in out

    ecritures = session.exec(
        select(Ecriture).where(Ecriture.association_id == assoc)
    ).all()
    created = [e for e in ecritures if e.statut == EcritureStatut.BROUILLON]
    assert len(created) == 1
    # MCP never validates: the entry stays a draft for a human to confirm.
    assert created[0].statut == EcritureStatut.BROUILLON


def test_saisir_recette_rejects_depense_category(session: Session):
    client, assoc = _admin_with_association("adm7@a.com", "A7")
    # Create a dépense category and try to book a recette with it → error.
    client.post(
        f"/api/asso/{assoc}/categories",
        json={"sens": "depense", "libelle": "MCP Dépense"},
    )
    key = _key_for_member(client, assoc)

    with pytest.raises(ToolError):
        run_tool(
            key,
            "saisir_recette",
            {"montant": 10, "categorie": "MCP Dépense", "compte_tresorerie": "Banque"},
        )


def test_creer_tiers_via_mcp(session: Session):
    client, assoc = _admin_with_association("adm8@a.com", "A8")
    key = _key_for_member(client, assoc)

    out = run_tool(key, "creer_tiers", {"nom": "Fournisseur X", "type": "fournisseur"})
    assert "Fournisseur X" in out


def test_unknown_tool_rejected(session: Session):
    client, assoc = _admin_with_association("adm9@a.com", "A9")
    key = _key_for_member(client, assoc)
    with pytest.raises(ToolError):
        run_tool(key, "supprimer_tout", {})


# --- Transport auth gate -------------------------------------------------


def test_mcp_endpoint_requires_api_key(session: Session):
    """The /mcp ASGI entrypoint rejects an unauthenticated request (401)."""
    import main

    transport = TestClient(main.app)
    resp = transport.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
    assert resp.status_code == 401
    resp2 = transport.post(
        "/mcp",
        headers={"X-API-Key": "abk_invalid"},
        json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
    )
    assert resp2.status_code == 401
