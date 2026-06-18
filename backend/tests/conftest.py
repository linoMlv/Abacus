import os

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from database import get_session

# Import the FastAPI instance, not the top-level ASGI wrapper that fronts /mcp.
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


@pytest.fixture(name="auth")
def auth_fixture(client: TestClient):
    """An authenticated client. Returns (client, association_id).

    Signs up an association and logs in; the TestClient persists the auth
    cookie across subsequent requests within the test.
    """
    signup = client.post(
        "/api/signup",
        json={
            "name": "AuthAsso",
            "email": "auth@example.com",
            "password": "password123",
            "balances": [{"name": "Main", "amount": "100.0"}],
        },
    )
    assert signup.status_code == 200, signup.text
    association_id = signup.json()["id"]

    login = client.post(
        "/api/login", json={"name": "AuthAsso", "password": "password123"}
    )
    assert login.status_code == 200, login.text
    return client, association_id
