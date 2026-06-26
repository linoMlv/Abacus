"""Security headers: present on every response, SPA vs docs CSP, no dev HSTS."""


def test_security_headers_on_a_normal_response(client):
    resp = client.get("/health")
    assert resp.status_code == 200

    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"

    csp = resp.headers["Content-Security-Policy"]
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "object-src 'none'" in csp
    # The strict SPA policy does not allow external scripts.
    assert "cdn.jsdelivr.net" not in csp


def test_headers_present_even_on_unauthorized_api_calls(client):
    resp = client.get("/api/asso/whatever/comptes")
    assert resp.status_code == 401
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert "default-src 'self'" in resp.headers["Content-Security-Policy"]


def test_docs_get_a_dedicated_relaxed_csp(client):
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    # Swagger/ReDoc need their CDN assets, so the docs CSP allows jsDelivr.
    assert "cdn.jsdelivr.net" in resp.headers["Content-Security-Policy"]


def test_hsts_is_not_sent_in_development(client):
    # The test environment is "development": HSTS must never be emitted there.
    resp = client.get("/health")
    assert "Strict-Transport-Security" not in resp.headers
