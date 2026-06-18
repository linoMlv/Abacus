"""
Abacus Remote MCP Server — integrated into FastAPI.

Exposes accounting tools over Streamable HTTP transport at /mcp.
Authenticated via X-API-Key header (same keys as the REST API).

Client configuration example (Claude Desktop / Claude Code):
{
  "mcpServers": {
    "abacus": {
      "type": "streamable-http",
      "url": "https://your-server.com/mcp",
      "headers": {
        "X-API-Key": "abk_..."
      }
    }
  }
}
"""

import hashlib
import json
import time
from contextvars import ContextVar
from datetime import UTC, datetime
from decimal import Decimal

from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.types import TextContent, Tool
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select
from starlette.requests import Request
from starlette.responses import JSONResponse

from database import engine
from models import ApiKey, Association, Balance, LogEntry, Operation, OperationType

# ContextVar to pass the authenticated association to tool handlers
_current_association: ContextVar[Association | None] = ContextVar(
    "_current_association", default=None
)


def _get_association_by_api_key(raw_key: str) -> Association | None:
    """Validate an API key and return the associated Association."""
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    with Session(engine) as session:
        api_key = session.exec(
            select(ApiKey).where(
                ApiKey.key_hash == key_hash, ApiKey.is_active.is_(True)
            )
        ).first()
        if not api_key:
            return None
        api_key.last_used_at = datetime.now(UTC)
        session.add(api_key)
        session.commit()

        association = session.exec(
            select(Association)
            .where(Association.id == api_key.association_id)
            .options(selectinload(Association.balances))
        ).first()
        return association


def _serialize(obj) -> str:
    """JSON-serialize with Decimal support."""

    def default(o):
        if isinstance(o, Decimal):
            return float(o)
        if isinstance(o, datetime):
            return o.isoformat()
        raise TypeError(f"Object of type {type(o)} is not JSON serializable")

    return json.dumps(obj, indent=2, default=default)


# ── Tool definitions ─────────────────────────────────────────────────────

TOOLS = [
    Tool(
        name="get_account_info",
        description=(
            "Get the current association's account information "
            "(name, email, balances)."
        ),
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="list_balances",
        description=(
            "List all balances (accounts) for the association "
            "with their current amounts."
        ),
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="create_balance",
        description="Create a new balance (account).",
        inputSchema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Balance name (e.g., 'Main Account')",
                },
                "initial_amount": {
                    "type": "number",
                    "description": "Initial amount in euros",
                },
            },
            "required": ["name", "initial_amount"],
        },
    ),
    Tool(
        name="update_balance",
        description="Update an existing balance's name, initial amount or position.",
        inputSchema={
            "type": "object",
            "properties": {
                "balance_id": {"type": "string"},
                "name": {"type": "string"},
                "initial_amount": {"type": "number"},
                "position": {"type": "integer"},
            },
            "required": ["balance_id", "name", "initial_amount", "position"],
        },
    ),
    Tool(
        name="delete_balance",
        description="Delete a balance. It must have no operations.",
        inputSchema={
            "type": "object",
            "properties": {"balance_id": {"type": "string"}},
            "required": ["balance_id"],
        },
    ),
    Tool(
        name="list_operations",
        description=(
            "List operations (transactions), optionally filtered by date range."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "start_date": {
                    "type": "string",
                    "description": "ISO date, e.g. 2024-01-01T00:00:00",
                },
                "end_date": {
                    "type": "string",
                    "description": "ISO date, e.g. 2024-12-31T23:59:59",
                },
            },
        },
    ),
    Tool(
        name="get_balance_operations",
        description="Get all operations for a specific balance.",
        inputSchema={
            "type": "object",
            "properties": {"balance_id": {"type": "string"}},
            "required": ["balance_id"],
        },
    ),
    Tool(
        name="create_operation",
        description="Create a new operation (income or expense).",
        inputSchema={
            "type": "object",
            "properties": {
                "balance_id": {"type": "string"},
                "name": {"type": "string", "description": "Short title"},
                "description": {"type": "string"},
                "group": {
                    "type": "string",
                    "description": "Category (e.g., 'Supplies')",
                },
                "amount": {
                    "type": "number",
                    "description": "Amount in euros (positive)",
                },
                "type": {"type": "string", "enum": ["income", "expense"]},
                "date": {"type": "string", "description": "ISO date"},
                "invoice": {
                    "type": "string",
                    "description": "Optional invoice reference",
                },
            },
            "required": [
                "balance_id",
                "name",
                "description",
                "group",
                "amount",
                "type",
                "date",
            ],
        },
    ),
    Tool(
        name="update_operation",
        description="Update an existing operation.",
        inputSchema={
            "type": "object",
            "properties": {
                "operation_id": {"type": "string"},
                "balance_id": {"type": "string"},
                "name": {"type": "string"},
                "description": {"type": "string"},
                "group": {"type": "string"},
                "amount": {"type": "number"},
                "type": {"type": "string", "enum": ["income", "expense"]},
                "date": {"type": "string"},
                "invoice": {"type": "string"},
            },
            "required": [
                "operation_id",
                "balance_id",
                "name",
                "description",
                "group",
                "amount",
                "type",
                "date",
            ],
        },
    ),
    Tool(
        name="delete_operation",
        description="Delete an operation by ID.",
        inputSchema={
            "type": "object",
            "properties": {"operation_id": {"type": "string"}},
            "required": ["operation_id"],
        },
    ),
]


# ── Tool implementations ─────────────────────────────────────────────────


def _exec_tool(name: str, args: dict, association: Association) -> str:
    with Session(engine) as session:
        if name == "get_account_info":
            return _serialize(
                {
                    "id": association.id,
                    "name": association.name,
                    "email": association.email,
                    "balances": [
                        {
                            "id": b.id,
                            "name": b.name,
                            "initialAmount": b.initialAmount,
                            "position": b.position,
                        }
                        for b in sorted(association.balances, key=lambda b: b.position)
                    ],
                }
            )

        if name == "list_balances":
            return _serialize(
                [
                    {
                        "id": b.id,
                        "name": b.name,
                        "initialAmount": b.initialAmount,
                        "position": b.position,
                    }
                    for b in sorted(association.balances, key=lambda b: b.position)
                ]
            )

        if name == "create_balance":
            max_pos = max((b.position for b in association.balances), default=-1)
            balance = Balance(
                name=args["name"],
                initialAmount=Decimal(str(args["initial_amount"])),
                association_id=association.id,
                position=max_pos + 1,
            )
            session.add(balance)
            session.commit()
            session.refresh(balance)
            return _serialize(
                {
                    "id": balance.id,
                    "name": balance.name,
                    "initialAmount": balance.initialAmount,
                }
            )

        if name == "update_balance":
            balance = session.get(Balance, args["balance_id"])
            if not balance or balance.association_id != association.id:
                return _serialize({"error": "Balance not found or unauthorized"})
            balance.name = args["name"]
            balance.initialAmount = Decimal(str(args["initial_amount"]))
            balance.position = args["position"]
            session.add(balance)
            session.commit()
            session.refresh(balance)
            return _serialize(
                {
                    "id": balance.id,
                    "name": balance.name,
                    "initialAmount": balance.initialAmount,
                }
            )

        if name == "delete_balance":
            balance = session.get(Balance, args["balance_id"])
            if not balance or balance.association_id != association.id:
                return _serialize({"error": "Balance not found or unauthorized"})
            if balance.operations:
                return _serialize({"error": "Cannot delete balance with operations"})
            session.delete(balance)
            session.commit()
            return _serialize({"ok": True})

        if name == "list_operations":
            stmt = (
                select(Operation)
                .join(Balance)
                .where(Balance.association_id == association.id)
            )
            if args.get("start_date"):
                stmt = stmt.where(Operation.date >= args["start_date"])
            if args.get("end_date"):
                stmt = stmt.where(Operation.date <= args["end_date"])
            stmt = stmt.order_by(Operation.date.desc())
            ops = session.exec(stmt).all()
            return _serialize(
                [
                    {
                        "id": o.id,
                        "name": o.name,
                        "description": o.description,
                        "group": o.group,
                        "amount": o.amount,
                        "type": o.type.value,
                        "date": o.date,
                        "balance_id": o.balance_id,
                        "invoice": o.invoice,
                    }
                    for o in ops
                ]
            )

        if name == "get_balance_operations":
            balance = session.get(Balance, args["balance_id"])
            if not balance or balance.association_id != association.id:
                return _serialize({"error": "Balance not found or unauthorized"})
            ops = session.exec(
                select(Operation)
                .where(Operation.balance_id == args["balance_id"])
                .order_by(Operation.date.desc())
            ).all()
            return _serialize(
                [
                    {
                        "id": o.id,
                        "name": o.name,
                        "description": o.description,
                        "group": o.group,
                        "amount": o.amount,
                        "type": o.type.value,
                        "date": o.date,
                        "invoice": o.invoice,
                    }
                    for o in ops
                ]
            )

        if name == "create_operation":
            balance = session.get(Balance, args["balance_id"])
            if not balance or balance.association_id != association.id:
                return _serialize({"error": "Balance not found or unauthorized"})
            op = Operation(
                name=args["name"],
                description=args["description"],
                group=args["group"],
                amount=Decimal(str(args["amount"])),
                type=OperationType(args["type"]),
                date=args["date"],
                balance_id=args["balance_id"],
                invoice=args.get("invoice"),
            )
            session.add(op)
            session.commit()
            session.refresh(op)
            return _serialize(
                {
                    "id": op.id,
                    "name": op.name,
                    "amount": op.amount,
                    "type": op.type.value,
                }
            )

        if name == "update_operation":
            op = session.get(Operation, args["operation_id"])
            if not op:
                return _serialize({"error": "Operation not found"})
            balance = session.get(Balance, op.balance_id)
            if not balance or balance.association_id != association.id:
                return _serialize({"error": "Unauthorized"})
            new_balance = session.get(Balance, args["balance_id"])
            if not new_balance or new_balance.association_id != association.id:
                return _serialize({"error": "Target balance unauthorized"})
            op.name = args["name"]
            op.description = args["description"]
            op.group = args["group"]
            op.amount = Decimal(str(args["amount"]))
            op.type = OperationType(args["type"])
            op.date = args["date"]
            op.balance_id = args["balance_id"]
            op.invoice = args.get("invoice")
            session.add(op)
            session.commit()
            session.refresh(op)
            return _serialize(
                {
                    "id": op.id,
                    "name": op.name,
                    "amount": op.amount,
                    "type": op.type.value,
                }
            )

        if name == "delete_operation":
            op = session.get(Operation, args["operation_id"])
            if not op:
                return _serialize({"error": "Operation not found"})
            balance = session.get(Balance, op.balance_id)
            if not balance or balance.association_id != association.id:
                return _serialize({"error": "Unauthorized"})
            session.delete(op)
            session.commit()
            return _serialize({"ok": True})

    return _serialize({"error": f"Unknown tool: {name}"})


# ── MCP Server factory ───────────────────────────────────────────────────


def create_mcp_server() -> Server:
    """Create and configure the MCP Server instance with all tools."""
    server = Server("abacus-accounting")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return TOOLS

    @server.call_tool()
    async def call_tool(name: str, arguments: dict | None) -> list[TextContent]:
        association = _current_association.get()
        if not association:
            return [
                TextContent(
                    type="text",
                    text='{"error": "Unauthorized — invalid or missing API key"}',
                )
            ]

        result = _exec_tool(name, arguments or {}, association)
        return [TextContent(type="text", text=result)]

    return server


# ── Session manager (singleton) ──────────────────────────────────────────

_session_manager: StreamableHTTPSessionManager | None = None


def get_session_manager() -> StreamableHTTPSessionManager:
    """Return the singleton session manager, creating it on first call."""
    global _session_manager
    if _session_manager is None:
        server = create_mcp_server()
        _session_manager = StreamableHTTPSessionManager(
            app=server,
            stateless=True,
        )
    return _session_manager


# ── ASGI app for /mcp ───────────────────────────────────────────────────


async def mcp_asgi_app(scope, receive, send):
    """Authenticate via X-API-Key, then delegate to the MCP session manager."""
    if scope["type"] != "http":
        return

    start_time = time.time()
    request = Request(scope, receive)

    # Extract client info for logging
    ip_address = (
        (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
        or request.headers.get("x-real-ip")
        or (request.client.host if request.client else None)
    )
    user_agent = request.headers.get("user-agent")

    # Extract API key from header
    api_key_header = request.headers.get("x-api-key", "")
    if not api_key_header:
        response = JSONResponse({"error": "Missing X-API-Key header"}, status_code=401)
        await response(scope, receive, send)
        _log_mcp_request(
            request.method,
            401,
            None,
            ip_address,
            user_agent,
            start_time,
            "mcp_auth_failed",
            "Missing X-API-Key header",
        )
        return

    # Authenticate
    association = _get_association_by_api_key(api_key_header)
    if not association:
        response = JSONResponse({"error": "Invalid API key"}, status_code=401)
        await response(scope, receive, send)
        _log_mcp_request(
            request.method,
            401,
            None,
            ip_address,
            user_agent,
            start_time,
            "mcp_auth_failed",
            "Invalid API key",
        )
        return

    # Capture response status code from the ASGI send callable
    captured_status = [200]

    async def send_wrapper(message):
        if message.get("type") == "http.response.start":
            captured_status[0] = message.get("status", 200)
        await send(message)

    # Set the association in context for tool handlers
    token = _current_association.set(association)
    try:
        manager = get_session_manager()
        await manager.handle_request(scope, receive, send_wrapper)
    finally:
        _current_association.reset(token)
        _log_mcp_request(
            request.method,
            captured_status[0],
            association.name,
            ip_address,
            user_agent,
            start_time,
            "mcp_request",
        )


def _log_mcp_request(
    method: str,
    status_code: int,
    user: str | None,
    ip_address: str | None,
    user_agent: str | None,
    start_time: float,
    event_type: str,
    detail: str | None = None,
):
    """Write a LogEntry for an MCP request."""
    duration_ms = round((time.time() - start_time) * 1000, 2)
    try:
        with Session(engine) as session:
            session.add(
                LogEntry(
                    method=method,
                    path="/mcp",
                    status_code=status_code,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    user=user,
                    duration_ms=duration_ms,
                    event_type=event_type,
                    detail=detail,
                )
            )
            session.commit()
    except Exception:
        pass
