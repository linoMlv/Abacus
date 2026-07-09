"""Shared rate limiter.

Used to throttle abuse-prone auth endpoints (login, register, invitation accept,
token refresh) per client IP. The limiter is a singleton so the FastAPI app and
the routers share the same state. Complementary to the per-account lockout in the
identity layer: the IP throttle caps a single source, the lockout a single
account under distributed brute-force.

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

# Tight limit for credential-guessing surfaces (login, register, invitation accept).
AUTH_RATE_LIMIT = os.getenv("AUTH_RATE_LIMIT", "5/minute")
# Looser limit for token refresh: it needs a valid 256-bit cookie (not guessable),
# and legitimate multi-tab clients may refresh a few times around token expiry.
REFRESH_RATE_LIMIT = os.getenv("REFRESH_RATE_LIMIT", "30/minute")

limiter = Limiter(key_func=get_remote_address, enabled=RATE_LIMIT_ENABLED)
