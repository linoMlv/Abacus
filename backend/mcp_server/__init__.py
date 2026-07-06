"""Abacus MCP server (Phase 6, plan §7) — role-aware accounting tools.

Exposes read and assisted-write accounting tools over the MCP Streamable HTTP
transport at ``/mcp``, authenticated by an ``X-API-Key`` header. A key is bound
to a member (:mod:`api_auth`); the server advertises and runs only the tools
that member's effective permissions allow. There is deliberately no tool to
validate, delete or close — entries created via MCP are always brouillon.

Wiring, matching the app's original integration:

* :func:`get_session_manager` — the singleton Streamable HTTP session manager;
  its ``run()`` context is entered by the FastAPI lifespan.
* :func:`handle_mcp` — the ASGI entrypoint for ``/mcp``. It authenticates the
  key up front (401 otherwise), binds it to a context var, then delegates to the
  session manager. Mounted *before* the FastAPI middleware stack so streaming is
  not buffered and the browser-oriented CSP/CSRF middleware does not apply.
"""

from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.types import TextContent, Tool
from starlette.responses import JSONResponse

from api_auth import resolve_api_key

from .context import (
    current_api_key,
    extract_api_key,
    reset_api_key,
    set_current_api_key,
)
from .dispatch import ToolError, available_tools_for_key, run_tool
from .session import new_session

__all__ = ["get_session_manager", "handle_mcp"]


def _build_server() -> Server:
    server = Server("abacus")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name=spec.name,
                description=spec.description,
                inputSchema=spec.input_schema,
            )
            for spec in available_tools_for_key(current_api_key())
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict | None) -> list[TextContent]:
        try:
            text = run_tool(current_api_key(), name, arguments)
        except ToolError as exc:
            # Surface a clean, French, user-facing message to the assistant.
            return [TextContent(type="text", text=f"Erreur : {exc}")]
        return [TextContent(type="text", text=text)]

    return server


_session_manager: StreamableHTTPSessionManager | None = None


def get_session_manager() -> StreamableHTTPSessionManager:
    """Return the singleton session manager (created on first use)."""
    global _session_manager
    if _session_manager is None:
        _session_manager = StreamableHTTPSessionManager(
            app=_build_server(),
            event_store=None,
            json_response=True,
            stateless=True,
        )
    return _session_manager


def _key_is_valid(raw_key: str | None) -> bool:
    with new_session() as session:
        return resolve_api_key(session, raw_key, touch=False) is not None


async def handle_mcp(scope, receive, send) -> None:
    """ASGI entrypoint for ``/mcp``: authenticate, then delegate to MCP."""
    if scope["type"] != "http":
        return

    raw_key = extract_api_key(scope)
    if not _key_is_valid(raw_key):
        await JSONResponse({"error": "Clé API absente ou invalide."}, status_code=401)(
            scope, receive, send
        )
        return

    token = set_current_api_key(raw_key)
    try:
        await get_session_manager().handle_request(scope, receive, send)
    finally:
        reset_api_key(token)
