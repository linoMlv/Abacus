"""In-memory per-IP throttle for the ``/mcp`` transport.

``/mcp`` is mounted at the ASGI top level, before the FastAPI middleware stack,
so the slowapi limiter used by the REST auth routes does not apply. This tiny
dependency-free sliding-window limiter fills the gap: it caps how many requests
a single client IP may make within a window, in the event loop's single thread.

Honours ``RATE_LIMIT_ENABLED`` (off in tests) and is configurable via
``MCP_RATE_LIMIT`` (requests) and ``MCP_RATE_WINDOW`` (seconds).
"""

import os
import time
from collections import defaultdict, deque

from rate_limit import RATE_LIMIT_ENABLED

MCP_RATE_LIMIT = int(os.getenv("MCP_RATE_LIMIT", "60"))
MCP_RATE_WINDOW = int(os.getenv("MCP_RATE_WINDOW", "60"))


class SlidingWindowLimiter:
    """Allow at most ``limit`` events per ``window`` seconds, per key."""

    def __init__(self, limit: int, window: int) -> None:
        self.limit = limit
        self.window = window
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        hits = self._hits[key]
        cutoff = now - self.window
        while hits and hits[0] <= cutoff:
            hits.popleft()
        if len(hits) >= self.limit:
            return False
        hits.append(now)
        return True


_limiter = SlidingWindowLimiter(MCP_RATE_LIMIT, MCP_RATE_WINDOW)


def _client_key(scope) -> str:
    client = scope.get("client")
    return client[0] if client else "unknown"


def allow_request(scope, now: float | None = None) -> bool:
    """True if this ``/mcp`` request is within the client's IP rate budget."""
    if not RATE_LIMIT_ENABLED or MCP_RATE_LIMIT <= 0:
        return True
    return _limiter.allow(_client_key(scope), now)
