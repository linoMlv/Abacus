from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from mcp_server import get_session_manager, mcp_asgi_app
from middleware import LoggingMiddleware
from routers import account, api_keys, associations, auth, balances, logs, operations


@asynccontextmanager
async def lifespan(app: FastAPI):
    session_manager = get_session_manager()
    async with session_manager.run():
        yield


_fastapi_app = FastAPI(lifespan=lifespan)

origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://localhost:9873",
]

_fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

# Logging middleware
_fastapi_app.add_middleware(LoggingMiddleware)

# Include routers
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


# Top-level ASGI app: intercepts /mcp before FastAPI's middleware stack,
# which would otherwise buffer SSE streaming responses.
async def app(scope, receive, send):
    if scope["type"] == "http" and scope["path"] == "/mcp":
        await mcp_asgi_app(scope, receive, send)
    else:
        await _fastapi_app(scope, receive, send)  # lifespan events also go here
