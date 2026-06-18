"""Small request helpers shared across the app."""

from starlette.requests import Request


def client_ip(request: Request) -> str | None:
    """Best-effort client IP, honoring reverse-proxy headers."""
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip
    return request.client.host if request.client else None
