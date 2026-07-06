"""Authorization-and-execution core for MCP tools (transport-agnostic).

Isolated from the MCP SDK wiring so it can be unit-tested directly with a raw
key. On every call it opens a fresh session, re-resolves the key (authority is
always current), enforces the tool's declared permission server-side, runs the
handler and — for writes — records an ``mcp.tool_call`` audit entry.
"""

from fastapi import HTTPException

from api_auth import resolve_api_key
from audit import AuditAction, record_audit
from auth_context import AccessContext
from authz import Permission

from .handlers import ToolError
from .serialization import to_text
from .session import new_session
from .tools import TOOL_SPECS, TOOLS_BY_NAME, ToolSpec


class ToolAuthError(ToolError):
    """The API key is missing, invalid or revoked."""


def available_tools(ctx: AccessContext | None) -> list[ToolSpec]:
    """The tools a context may see: those its effective permissions allow."""
    if ctx is None:
        return []
    return [spec for spec in TOOL_SPECS if spec.permission in ctx.permissions]


def available_tools_for_key(raw_key: str | None) -> list[ToolSpec]:
    """Advertised tools for a raw key (read-only; does not stamp last_used)."""
    with new_session() as session:
        ctx = resolve_api_key(session, raw_key, touch=False)
        return available_tools(ctx)


def run_tool(raw_key: str | None, name: str, arguments: dict | None) -> str:
    """Authorize and run tool ``name``; return its result as JSON text.

    Raises :class:`ToolAuthError` for an invalid key and :class:`ToolError` for a
    forbidden tool, an unknown tool, or a handler-reported problem.
    """
    spec = TOOLS_BY_NAME.get(name)
    if spec is None:
        raise ToolError(f"Outil inconnu : {name!r}.")

    with new_session() as session:
        ctx = resolve_api_key(session, raw_key)
        if ctx is None:
            raise ToolAuthError("Clé API invalide ou révoquée.")
        if spec.permission not in ctx.permissions:
            raise ToolError(
                f"L'outil {name!r} requiert la permission {spec.permission.value!r}, "
                "non accordée à cette clé."
            )

        try:
            result = spec.handler(ctx, session, arguments or {})
        except HTTPException as exc:
            # Reused routes signal tenant/validation problems as HTTP errors;
            # surface their (safe, French) detail to the assistant.
            raise ToolError(str(exc.detail)) from exc

        if spec.writes:
            record_audit(
                session,
                association_id=ctx.association_id,
                actor_user_id=ctx.user.id,
                action=AuditAction.MCP_TOOL_CALL,
                target_type="mcp_tool",
                target_id=None,
                detail=name,
            )
            session.commit()

        return to_text(result)


__all__ = [
    "Permission",
    "ToolAuthError",
    "ToolError",
    "available_tools",
    "available_tools_for_key",
    "run_tool",
]
