from fastapi.testclient import TestClient


def test_signup(client: TestClient):
    response = client.post(
        "/api/signup",
        json={
            "name": "TestAsso",
            "email": "test@example.com",
            "password": "password123",
            "balances": [{"name": "Main", "amount": "100.0"}],
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["name"] == "TestAsso"
    assert data["email"] == "test@example.com"
    assert len(data["balances"]) == 1
    assert data["balances"][0]["name"] == "Main"
    # Decimal fields are serialized as JSON strings by Pydantic.
    assert float(data["balances"][0]["initialAmount"]) == 100.0


def test_signup_duplicate_name(client: TestClient):
    payload = {
        "name": "DupName",
        "email": "a@example.com",
        "password": "password123",
        "balances": [],
    }
    assert client.post("/api/signup", json=payload).status_code == 200
    payload["email"] = "b@example.com"
    response = client.post("/api/signup", json=payload)
    assert response.status_code == 400


def test_signup_duplicate_email(client: TestClient):
    payload = {
        "name": "NameA",
        "email": "dup@example.com",
        "password": "password123",
        "balances": [],
    }
    assert client.post("/api/signup", json=payload).status_code == 200
    payload["name"] = "NameB"
    response = client.post("/api/signup", json=payload)
    assert response.status_code == 400


def test_login(client: TestClient):
    client.post(
        "/api/signup",
        json={
            "name": "LoginAsso",
            "email": "login@example.com",
            "password": "password123",
            "balances": [],
        },
    )

    response = client.post(
        "/api/login", json={"name": "LoginAsso", "password": "password123"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert "access_token" in response.cookies


def test_login_wrong_password(client: TestClient):
    client.post(
        "/api/signup",
        json={
            "name": "WrongPass",
            "email": "wrong@example.com",
            "password": "password123",
            "balances": [],
        },
    )
    response = client.post("/api/login", json={"name": "WrongPass", "password": "nope"})
    assert response.status_code == 401


def test_login_unknown_user(client: TestClient):
    response = client.post("/api/login", json={"name": "ghost", "password": "whatever"})
    assert response.status_code == 401


def test_me_requires_auth(client: TestClient):
    assert client.get("/api/me").status_code == 401


def test_me_authenticated(auth):
    client, association_id = auth
    response = client.get("/api/me")
    assert response.status_code == 200
    assert response.json()["id"] == association_id


def test_logout_clears_cookie(auth):
    client, _ = auth
    response = client.post("/api/logout")
    assert response.status_code == 200
    # After logout the session cookie must no longer authenticate.
    client.cookies.clear()
    assert client.get("/api/me").status_code == 401
