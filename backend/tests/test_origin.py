from fastapi.testclient import TestClient


def test_disallowed_origin_is_rejected(client: TestClient):
    response = client.post(
        "/api/login",
        json={"name": "x", "password": "y"},
        headers={"Origin": "http://evil.example.com"},
    )
    assert response.status_code == 403


def test_allowed_origin_passes_through(client: TestClient):
    # Allowed origin: the request reaches the handler (401 for bad creds,
    # which is what matters here: it is not blocked as 403).
    response = client.post(
        "/api/login",
        json={"name": "x", "password": "y"},
        headers={"Origin": "http://localhost:9873"},
    )
    assert response.status_code != 403


def test_no_origin_header_passes_through(client: TestClient):
    # Non-browser clients (e.g. API-key callers) send no Origin.
    response = client.post("/api/login", json={"name": "x", "password": "y"})
    assert response.status_code != 403
