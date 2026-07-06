"""Per-request authentication context for the MCP server.

The raw ``X-API-Key`` is captured from the ASGI scope by the transport wrapper
and stored in a :class:`~contextvars.ContextVar`. Tool dispatch re-resolves it
against a fresh DB session on every call, so authority is always current
(revocation, suspension and permission changes take effect immediately) and no
ORM object outlives its session.
"""

from contextvars import ContextVar, Token

from api_auth import API_KEY_HEADER

# The raw API key of the in-flight MCP request (set by the transport wrapper).
_current_api_key: ContextVar[str | None] = ContextVar("_current_api_key", default=None)


def set_current_api_key(raw_key: str | None) -> Token:
    """Bind the request's key; returns a token to :func:`reset_api_key` with."""
    return _current_api_key.set(raw_key)


def reset_api_key(token: Token) -> None:
    _current_api_key.reset(token)


def current_api_key() -> str | None:
    return _current_api_key.get()


def extract_api_key(scope) -> str | None:
    """Read the ``X-API-Key`` header from a raw ASGI ``scope``."""
    wanted = API_KEY_HEADER.lower().encode()
    for name, value in scope.get("headers", []):
        if name.lower() == wanted:
            return value.decode("latin-1")
    return None
