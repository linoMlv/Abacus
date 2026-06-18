"""Serve the built frontend (SPA) from FastAPI.

In the container, the Vite build is copied next to the backend and mounted at
"/". Deep links fall back to index.html; API/asset 404s are preserved so they
are not masked by the SPA shell. In development the directory is absent, so the
mount is skipped and the Vite dev server serves the frontend instead.
"""

import os

from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.staticfiles import StaticFiles

RESERVED_PREFIXES = ("api", "health", "mcp")


def _should_fallback(path: str) -> bool:
    # Never mask backend 404s, nor missing files (paths with an extension),
    # with the SPA shell. Match the first path segment so a client route like
    # "apikeys" is not mistaken for the "api" prefix.
    if path.split("/", 1)[0] in RESERVED_PREFIXES:
        return False
    last_segment = path.rsplit("/", 1)[-1]
    return "." not in last_segment


class SPAStaticFiles(StaticFiles):
    async def get_response(self, path, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404 and _should_fallback(path):
                return await super().get_response("index.html", scope)
            raise


def mount_frontend(app, directory: str) -> bool:
    """Mount the SPA at '/' if the build directory exists. Returns True if mounted.

    Must be called after all API routes are registered so they take precedence.
    """
    if not directory or not os.path.isdir(directory):
        return False
    app.mount("/", SPAStaticFiles(directory=directory, html=True), name="spa")
    return True
