import asyncio
import logging
import os
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlmodel import Session

import mcp_server
from database import engine
from log_retention import purge_old_logs
from middleware import (
    LoggingMiddleware,
    OriginValidationMiddleware,
    SecurityHeadersMiddleware,
)
from rate_limit import limiter
from routers import (
    accounting,
    annexe,
    apikeys,
    banque,
    budget,
    categories,
    comptes,
    ecritures,
    evenements,
    exercices,
    exports,
    identity,
    justificatifs,
    logs,
    permissions,
    recurrences,
    recus,
    synthese,
    tiers,
    tresorerie,
    tva,
)
from scheduler import recurrences_daily_loop
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
    # Daily job booking recurring entries that have fallen due (no cron in the
    # container). Runs a pass at startup, then every 24 h, over all associations.
    scheduler_task = asyncio.create_task(recurrences_daily_loop())
    # The MCP session manager must run for the app's lifetime (Streamable HTTP).
    async with mcp_server.get_session_manager().run():
        try:
            yield
        finally:
            scheduler_task.cancel()
            with suppress(asyncio.CancelledError):
                await scheduler_task


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
_fastapi_app.include_router(comptes.router)
_fastapi_app.include_router(exercices.router)
_fastapi_app.include_router(annexe.router)
_fastapi_app.include_router(ecritures.router)
_fastapi_app.include_router(tresorerie.router)
_fastapi_app.include_router(banque.router)
_fastapi_app.include_router(recurrences.router)
_fastapi_app.include_router(recus.router)
_fastapi_app.include_router(budget.router)
_fastapi_app.include_router(categories.router)
_fastapi_app.include_router(tiers.router)
_fastapi_app.include_router(evenements.router)
_fastapi_app.include_router(synthese.router)
_fastapi_app.include_router(tva.router)
_fastapi_app.include_router(permissions.router)
_fastapi_app.include_router(apikeys.router)
_fastapi_app.include_router(exports.router)
_fastapi_app.include_router(justificatifs.router)
_fastapi_app.include_router(logs.router)


@_fastapi_app.get("/health")
def health_check():
    return {"status": "ok"}


# Serve the built frontend (mounted last so API routes take precedence).
# Skipped in development when the build directory is absent.
mount_frontend(_fastapi_app, os.getenv("FRONTEND_DIST", "static"))


# Top-level ASGI app: intercept /mcp before FastAPI's middleware stack (the
# browser-oriented CSP/CSRF middleware must not apply to the machine MCP
# transport, and its streaming must not be buffered). Everything else — including
# lifespan events — goes to the FastAPI app.
async def app(scope, receive, send):
    if scope["type"] == "http" and (
        scope["path"] == "/mcp" or scope["path"].startswith("/mcp/")
    ):
        await mcp_server.handle_mcp(scope, receive, send)
    else:
        await _fastapi_app(scope, receive, send)
