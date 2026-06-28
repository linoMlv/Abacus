import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlmodel import Session

from database import engine
from log_retention import purge_old_logs
from mcp_server import get_session_manager, mcp_asgi_app
from middleware import (
    LoggingMiddleware,
    OriginValidationMiddleware,
    SecurityHeadersMiddleware,
)
from rate_limit import limiter
from routers import (
    account,
    accounting,
    api_keys,
    associations,
    auth,
    balances,
    categories,
    ecritures,
    identity,
    justificatifs,
    logs,
    operations,
    tiers,
    tresorerie,
)
from security import ENVIRONMENT
from static_files import mount_frontend

DEFAULT_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://localhost:9873",
]


def _allowed_origins() -> list[str]:
    """Allowed browser origins, from CORS_ORIGINS (comma-separated) or dev defaults."""
    raw = os.getenv("CORS_ORIGINS")
    if raw:
        return [o.strip() for o in raw.split(",") if o.strip()]
    if ENVIRONMENT == "production":
        logging.warning(
            "CORS_ORIGINS is not set in production; falling back to localhost "
            "origins. Browser POST/PUT/DELETE from the real domain will be "
            "rejected with 403 by the origin check. Set CORS_ORIGINS to your "
            "public URL (e.g. https://abacus.example.com)."
        )
    return DEFAULT_ORIGINS


@asynccontextmanager
async def lifespan(app: FastAPI):
    _purge_logs_on_startup()
    session_manager = get_session_manager()
    async with session_manager.run():
        yield


def _purge_logs_on_startup() -> None:
    """Best-effort log retention at startup; never block the app on failure."""
    try:
        with Session(engine) as session:
            purge_old_logs(session)
    except Exception:
        logging.getLogger(__name__).warning("Log purge skipped", exc_info=True)


_fastapi_app = FastAPI(lifespan=lifespan)

# Rate limiting (slowapi): the limiter is shared with the routers.
_fastapi_app.state.limiter = limiter
_fastapi_app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

origins = _allowed_origins()

_fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

# Reject cross-origin state-changing browser requests (CSRF defense in depth).
_fastapi_app.add_middleware(OriginValidationMiddleware, allowed_origins=origins)

# Logging middleware
_fastapi_app.add_middleware(LoggingMiddleware)

# Security headers (CSP, HSTS in prod, nosniff, framing/referrer protections).
_fastapi_app.add_middleware(SecurityHeadersMiddleware, hsts=ENVIRONMENT == "production")

# Include routers
_fastapi_app.include_router(identity.router)
_fastapi_app.include_router(accounting.router)
_fastapi_app.include_router(ecritures.router)
_fastapi_app.include_router(tresorerie.router)
_fastapi_app.include_router(categories.router)
_fastapi_app.include_router(tiers.router)
_fastapi_app.include_router(justificatifs.router)
_fastapi_app.include_router(auth.router)
_fastapi_app.include_router(associations.router)
_fastapi_app.include_router(operations.router)
_fastapi_app.include_router(balances.router)
_fastapi_app.include_router(logs.router)
_fastapi_app.include_router(account.router)
_fastapi_app.include_router(api_keys.router)


@_fastapi_app.get("/health")
def health_check():
    return {"status": "ok"}


# Serve the built frontend (mounted last so API routes take precedence).
# Skipped in development when the build directory is absent.
mount_frontend(_fastapi_app, os.getenv("FRONTEND_DIST", "static"))


# Top-level ASGI app: intercepts /mcp before FastAPI's middleware stack,
# which would otherwise buffer SSE streaming responses.
async def app(scope, receive, send):
    if scope["type"] == "http" and (
        scope["path"] == "/mcp" or scope["path"].startswith("/mcp/")
    ):
        await mcp_asgi_app(scope, receive, send)
    else:
        await _fastapi_app(scope, receive, send)  # lifespan events also go here
