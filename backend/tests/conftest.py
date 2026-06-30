import os

# Pin the test environment before the app is imported, so an ambient .env
# (e.g. a deployment file picked up by load_dotenv) cannot change behavior:
# load_dotenv runs with override=False and won't clobber these.
# - development: cookies are not Secure, so the http TestClient keeps them.
# - fixed CORS origins: deterministic origin-validation tests.
# - rate limiting off: the dedicated test re-enables the limiter explicitly.
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault(
    "CORS_ORIGINS",
    "http://localhost:5173,http://localhost:3000,http://localhost:9873",
)
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from database import get_session
from main import _fastapi_app as app

# Test database: defaults to in-memory SQLite for fast local runs.
# CI sets TEST_DATABASE_URL to a PostgreSQL instance to match production.
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "sqlite://")

if TEST_DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    engine = create_engine(TEST_DATABASE_URL)


@pytest.fixture(name="session")
def session_fixture():
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override

    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()
