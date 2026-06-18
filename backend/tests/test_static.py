from fastapi import FastAPI
from fastapi.testclient import TestClient

from static_files import mount_frontend


def _build_app(tmp_path):
    (tmp_path / "index.html").write_text("<html><body>app shell</body></html>")
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "app.js").write_text("console.log('hi')")

    app = FastAPI()

    @app.get("/api/ping")
    def ping():
        return {"ok": True}

    assert mount_frontend(app, str(tmp_path)) is True
    return TestClient(app)


def test_serves_index_at_root(tmp_path):
    client = _build_app(tmp_path)
    response = client.get("/")
    assert response.status_code == 200
    assert "app shell" in response.text


def test_serves_built_assets(tmp_path):
    client = _build_app(tmp_path)
    assert client.get("/assets/app.js").status_code == 200


def test_spa_deep_link_falls_back_to_index(tmp_path):
    client = _build_app(tmp_path)
    response = client.get("/logs")
    assert response.status_code == 200
    assert "app shell" in response.text


def test_api_route_still_served(tmp_path):
    client = _build_app(tmp_path)
    assert client.get("/api/ping").json() == {"ok": True}


def test_unknown_api_path_is_404_not_shell(tmp_path):
    client = _build_app(tmp_path)
    response = client.get("/api/unknown")
    assert response.status_code == 404
    assert "app shell" not in response.text


def test_missing_asset_is_404(tmp_path):
    client = _build_app(tmp_path)
    assert client.get("/missing.png").status_code == 404


def test_mount_skipped_when_directory_absent(tmp_path):
    app = FastAPI()
    assert mount_frontend(app, str(tmp_path / "does-not-exist")) is False
