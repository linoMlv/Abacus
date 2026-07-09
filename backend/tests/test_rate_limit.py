from fastapi.testclient import TestClient

from rate_limit import limiter


def test_auth_endpoints_are_rate_limited(client: TestClient):
    # The suite runs with the limiter disabled; enable it just for this test.
    # While disabled the limiter neither counts nor checks, so toggling it
    # here does not affect other tests.
    limiter.enabled = True
    try:
        # Login is rate-limited (AUTH_RATE_LIMIT, 5/minute). Bad credentials
        # reach the handler (401) until the limit kicks in; hammering it past
        # the limit must start returning 429.
        codes = [
            client.post(
                "/api/auth/login",
                json={"email": "x@example.com", "password": "nope"},
            ).status_code
            for _ in range(7)
        ]
    finally:
        limiter.enabled = False

    assert 429 in codes
    # At most the per-minute allowance reaches the handler before throttling.
    assert len([c for c in codes if c != 429]) <= 5


def test_register_is_rate_limited(client: TestClient):
    limiter.enabled = True
    try:
        codes = [
            client.post(
                "/api/auth/register",
                json={
                    "email": f"u{i}@example.com",
                    "password": "password123",
                    "name": "U",
                },
            ).status_code
            for i in range(7)
        ]
    finally:
        limiter.enabled = False

    assert 429 in codes
