"""Database session opener for MCP calls.

The MCP transport is not a FastAPI route, so it cannot rely on the request-scoped
``get_session`` dependency: each tool call opens its own short-lived session
here. Kept as a single indirection so tests can bind MCP calls to their own
engine (``engine`` is read at call time).
"""

from sqlmodel import Session

from database import engine


def new_session() -> Session:
    """Open a fresh session on the configured engine."""
    return Session(engine)
