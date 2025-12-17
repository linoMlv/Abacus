from fastapi.testclient import TestClient


def test_signup(client: TestClient):
    response = client.post(
        "/api/signup",
        json={
            "name": "TestAsso",
            "password": "password123",
            "balances": [{"name": "Main", "amount": "100.0"}],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "TestAsso"
    assert len(data["balances"]) == 1
    assert data["balances"][0]["name"] == "Main"
    assert data["balances"][0]["initialAmount"] == 100.0


def test_login(client: TestClient):
    # First signup
    client.post(
        "/api/signup",
        json={"name": "LoginAsso", "password": "password123", "balances": []},
    )

    # Then login
    response = client.post(
        "/api/login", json={"name": "LoginAsso", "password": "password123"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

    # Check cookie
    assert "access_token" in response.cookies
