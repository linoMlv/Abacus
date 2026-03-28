import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from middleware import LoggingMiddleware
from routers import associations, auth, balances, logs, operations

app = FastAPI()

origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://localhost:9873",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

# Logging middleware
app.add_middleware(LoggingMiddleware)

# Include routers
app.include_router(auth.router)
app.include_router(associations.router)
app.include_router(operations.router)
app.include_router(balances.router)
app.include_router(logs.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}


# Static files (Frontend build serving)
static_dir = "static"
if os.path.exists(static_dir):
    @app.get("/logs")
    def serve_logs_spa():
        return FileResponse(os.path.join(static_dir, "index.html"))

    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
