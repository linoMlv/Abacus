import json
import time

from jose import JWTError, jwt
from sqlmodel import Session
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from database import engine
from models import LogEntry
from request_utils import client_ip
from security import ALGORITHM, SECRET_KEY


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach defense-in-depth security headers to every response.

    A strict Content-Security-Policy is applied to the SPA and the API; the
    interactive API docs (Swagger/ReDoc) need their CDN assets, so the few docs
    paths get a dedicated, slightly looser policy. ``setdefault`` is used so a
    route may override a header deliberately. HSTS is only emitted in production
    (it must never be sent over plain HTTP in development).
    """

    # SPA: external bundled JS only; inline styles are allowed because Radix/
    # shadcn inject style attributes at runtime.
    _SPA_CSP = "; ".join(
        [
            "default-src 'self'",
            "base-uri 'self'",
            "script-src 'self'",
            "style-src 'self' 'unsafe-inline'",
            "img-src 'self' data:",
            "font-src 'self' data:",
            "connect-src 'self'",
            "object-src 'none'",
            "frame-ancestors 'none'",
            "form-action 'self'",
        ]
    )
    # Swagger UI / ReDoc load scripts and styles from jsDelivr.
    _DOCS_CSP = "; ".join(
        [
            "default-src 'self'",
            "base-uri 'self'",
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",
            "img-src 'self' data: https://cdn.jsdelivr.net https://fastapi.tiangolo.com",
            "worker-src 'self' blob:",
            "object-src 'none'",
            "frame-ancestors 'none'",
        ]
    )
    _DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")

    def __init__(self, app, hsts: bool):
        super().__init__(app)
        self.hsts = hsts

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        is_docs = request.url.path.startswith(self._DOCS_PATHS)
        response.headers.setdefault(
            "Content-Security-Policy", self._DOCS_CSP if is_docs else self._SPA_CSP
        )
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault(
            "Referrer-Policy", "strict-origin-when-cross-origin"
        )
        response.headers.setdefault("X-Frame-Options", "DENY")
        if self.hsts:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=63072000; includeSubDomains",
            )
        return response


class OriginValidationMiddleware(BaseHTTPMiddleware):
    """Reject state-changing browser requests from an unexpected origin.

    A defense-in-depth measure against CSRF on cookie-authenticated requests.
    Only enforced when an Origin header is present, so non-browser clients
    (e.g. API-key callers, which send no Origin) are unaffected.
    """

    UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

    def __init__(self, app, allowed_origins):
        super().__init__(app)
        self.allowed_origins = set(allowed_origins)

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method in self.UNSAFE_METHODS:
            origin = request.headers.get("origin")
            if origin and origin not in self.allowed_origins:
                return JSONResponse(
                    status_code=403, content={"detail": "Origin not allowed"}
                )
        return await call_next(request)


class LoggingMiddleware(BaseHTTPMiddleware):
    # Only /api requests are logged; /api/logs is excluded to avoid noise.
    EXCLUDED_PREFIXES = ("/api/logs",)

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        # Skip non-API paths (static files) and explicitly excluded prefixes.
        if not path.startswith("/api") or any(
            path.startswith(p) for p in self.EXCLUDED_PREFIXES
        ):
            return await call_next(request)

        start_time = time.time()

        # Extract the submitted email from login/register bodies before they
        # are consumed downstream.
        body_user = None
        if request.method == "POST" and path in (
            "/api/auth/login",
            "/api/auth/register",
        ):
            try:
                body_user = json.loads(await request.body()).get("email")
            except Exception:
                pass

        response = await call_next(request)

        duration_ms = (time.time() - start_time) * 1000

        # Determine event type and user
        event_type = "request"
        user = _extract_user_from_cookie(request)
        detail = None

        if path == "/api/auth/login" and request.method == "POST":
            user = body_user
            if response.status_code == 200:
                event_type = "login"
            else:
                event_type = "login_failed"
                detail = f"HTTP {response.status_code}"
        elif path == "/api/auth/logout" and request.method == "POST":
            event_type = "logout"
        elif path == "/api/auth/register" and request.method == "POST":
            user = body_user
            if response.status_code == 201:
                event_type = "register"
            else:
                event_type = "register_failed"
                detail = f"HTTP {response.status_code}"

        ip_address = client_ip(request)
        user_agent = request.headers.get("user-agent")

        log_entry = LogEntry(
            method=request.method,
            path=path,
            status_code=response.status_code,
            ip_address=ip_address,
            user_agent=user_agent,
            user=user,
            association_id=_association_id_from_path(path),
            duration_ms=round(duration_ms, 2),
            event_type=event_type,
            detail=detail,
        )

        try:
            with Session(engine) as session:
                session.add(log_entry)
                session.commit()
        except Exception:
            pass  # Don't let logging failures break the app

        return response


def _association_id_from_path(path: str) -> str | None:
    """Return the association id of a tenant-scoped path /api/asso/{id}/...

    Recorded for any such request (even 403/404), giving an admin visibility on
    access attempts against their association. Never leaks across tenants: the
    logs endpoint filters on the reader's own association id.
    """
    parts = path.split("/")
    if len(parts) >= 4 and parts[1] == "api" and parts[2] == "asso" and parts[3]:
        return parts[3]
    return None


def _extract_user_from_cookie(request: Request) -> str | None:
    token = request.cookies.get("access_token")
    if not token:
        return None
    if token.startswith("Bearer "):
        token = token[7:]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None
