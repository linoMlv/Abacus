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

        # Extract the submitted username from login/signup bodies before they
        # are consumed downstream.
        body_user = None
        if request.method == "POST" and path in ("/api/login", "/api/signup"):
            try:
                body_user = json.loads(await request.body()).get("name")
            except Exception:
                pass

        response = await call_next(request)

        duration_ms = (time.time() - start_time) * 1000

        # Determine event type and user
        event_type = "request"
        user = _extract_user_from_cookie(request)
        detail = None

        if path == "/api/login" and request.method == "POST":
            user = body_user
            if response.status_code == 200:
                event_type = "login"
            else:
                event_type = "login_failed"
                detail = f"HTTP {response.status_code}"
        elif path == "/api/logout" and request.method == "POST":
            event_type = "logout"
        elif path == "/api/signup" and request.method == "POST":
            user = body_user
            if response.status_code == 200:
                event_type = "signup"
            else:
                event_type = "signup_failed"
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
