from fastapi.testclient import TestClient


def test_create_and_list_api_key(auth):
    client, _ = auth
    created = client.post("/api/api-keys", json={"name": "ci-key"})
    assert created.status_code == 200, created.text
    data = created.json()
    assert data["key"].startswith("abk_")
    assert data["name"] == "ci-key"

    keys = client.get("/api/api-keys").json()
    assert len(keys) == 1
    # The raw key must never be returned again after creation.
    assert "key" not in keys[0]
    assert keys[0]["key_prefix"] == data["key_prefix"]


def test_api_key_authenticates_requests(auth):
    client, _ = auth
    raw_key = client.post("/api/api-keys", json={"name": "mcp"}).json()["key"]

    # Drop the session cookie: authenticate purely via the API key header.
    client.cookies.clear()
    response = client.get("/api/me", headers={"X-API-Key": raw_key})
    assert response.status_code == 200


def test_invalid_api_key_rejected(client: TestClient):
    response = client.get("/api/me", headers={"X-API-Key": "abk_invalid"})
    assert response.status_code == 401


def test_revoke_api_key(auth):
    client, _ = auth
    key_id = client.post("/api/api-keys", json={"name": "tmp"}).json()["id"]
    assert client.delete(f"/api/api-keys/{key_id}").status_code == 200
    assert client.get("/api/api-keys").json() == []
