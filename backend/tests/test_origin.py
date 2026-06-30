from fastapi.testclient import TestClient

# The origin check guards every state-changing request; we exercise it on the
# user login endpoint. Bad credentials are fine here — we only assert framing,
# i.e. whether the request is blocked as 403 before it reaches the handler.
_LOGIN = "/api/auth/login"
_CREDS = {"email": "x@example.com", "password": "y"}


def test_disallowed_origin_is_rejected(client: TestClient):
    response = client.post(
        _LOGIN,
        json=_CREDS,
        headers={"Origin": "http://evil.example.com"},
    )
    assert response.status_code == 403


def test_allowed_origin_passes_through(client: TestClient):
    # Allowed origin: the request reaches the handler (401 for bad creds,
    # which is what matters here: it is not blocked as 403).
    response = client.post(
        _LOGIN,
        json=_CREDS,
        headers={"Origin": "http://localhost:9873"},
    )
    assert response.status_code != 403


def test_no_origin_header_passes_through(client: TestClient):
    # Non-browser clients (e.g. server-to-server callers) send no Origin.
    response = client.post(_LOGIN, json=_CREDS)
    assert response.status_code != 403
