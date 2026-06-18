from fastapi.testclient import TestClient


def test_login_sets_refresh_cookie(auth):
    client, _ = auth
    assert client.cookies.get("refresh_token") is not None


def test_refresh_rotates_and_keeps_session(auth):
    client, association_id = auth
    old_refresh = client.cookies.get("refresh_token")

    response = client.post("/api/refresh")
    assert response.status_code == 200, response.text
    assert response.json()["association"]["id"] == association_id

    # The refresh token must have rotated.
    new_refresh = client.cookies.get("refresh_token")
    assert new_refresh and new_refresh != old_refresh

    # The new access cookie still authenticates.
    assert client.get("/api/me").status_code == 200


def test_rotated_refresh_token_is_revoked(auth):
    client, _ = auth
    old_refresh = client.cookies.get("refresh_token")

    assert client.post("/api/refresh").status_code == 200

    # Replaying the old (now rotated) refresh token must fail.
    client.cookies.set("refresh_token", old_refresh)
    assert client.post("/api/refresh").status_code == 401


def test_refresh_without_cookie_is_rejected(client: TestClient):
    assert client.post("/api/refresh").status_code == 401


def test_logout_revokes_refresh_token(auth):
    client, _ = auth
    refresh = client.cookies.get("refresh_token")

    assert client.post("/api/logout").status_code == 200

    # Even replaying the captured refresh token must fail after logout.
    client.cookies.set("refresh_token", refresh)
    assert client.post("/api/refresh").status_code == 401


def test_logout_all_revokes_every_session(auth):
    client, _ = auth
    refresh = client.cookies.get("refresh_token")

    assert client.post("/api/logout-all").status_code == 200

    client.cookies.set("refresh_token", refresh)
    assert client.post("/api/refresh").status_code == 401


def test_password_reset_revokes_refresh_sessions(auth):
    from jose import jwt

    from security import ALGORITHM, SECRET_KEY

    client, _ = auth
    refresh = client.cookies.get("refresh_token")

    reset_token = jwt.encode(
        {"sub": "AuthAsso", "purpose": "reset"}, SECRET_KEY, algorithm=ALGORITHM
    )
    response = client.post(
        "/api/reset-password",
        json={"token": reset_token, "password": "brand-new-password"},
    )
    assert response.status_code == 200

    # A refresh token issued before the reset must no longer be usable.
    client.cookies.set("refresh_token", refresh)
    assert client.post("/api/refresh").status_code == 401
