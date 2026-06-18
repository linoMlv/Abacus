"""Shared rate limiter.

Used to throttle abuse-prone endpoints (login, password reset). The limiter
is a singleton so the FastAPI app and the routers share the same state.

Disable it in tests with RATE_LIMIT_ENABLED=false.
"""

import os

from slowapi import Limiter
from slowapi.util import get_remote_address

RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() in (
    "1",
    "true",
    "yes",
)

# Limit applied to authentication endpoints, e.g. "5/minute".
AUTH_RATE_LIMIT = os.getenv("AUTH_RATE_LIMIT", "5/minute")

limiter = Limiter(key_func=get_remote_address, enabled=RATE_LIMIT_ENABLED)
