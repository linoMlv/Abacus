from fastapi.testclient import TestClient

from rate_limit import limiter


def test_auth_endpoints_are_rate_limited(client: TestClient):
    # The suite runs with the limiter disabled; enable it just for this test.
    # While disabled the limiter neither counts nor checks, so toggling it
    # here does not affect other tests.
    limiter.enabled = True
    try:
        # forgot-password always returns 200 and has no side effects, so it
        # is a safe endpoint to hammer past the default 5/minute limit.
        codes = [
            client.post(
                "/api/forgot-password", json={"email": "x@example.com"}
            ).status_code
            for _ in range(7)
        ]
    finally:
        limiter.enabled = False

    assert 429 in codes
    assert codes.count(200) <= 5
