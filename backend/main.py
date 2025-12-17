from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from routers import auth, operations, balances, associations

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
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(associations.router)
app.include_router(operations.router)
app.include_router(balances.router)

# Static files (Frontend build serving)
static_dir = "static"
if os.path.exists(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

@app.get("/health")
def health_check():
    return {"status": "ok"}
