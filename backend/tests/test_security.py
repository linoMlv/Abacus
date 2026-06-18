import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _import_security(env_extra):
    env = {"PATH": "/usr/bin:/bin"}
    env.update(env_extra)
    return subprocess.run(
        [sys.executable, "-c", "import security"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
    )


def test_production_rejects_default_secret_key():
    result = _import_security({"ENVIRONMENT": "production"})
    assert result.returncode != 0
    assert "SECRET_KEY" in result.stderr


def test_production_accepts_custom_secret_key():
    result = _import_security(
        {"ENVIRONMENT": "production", "SECRET_KEY": "a-very-secret-value"}
    )
    assert result.returncode == 0, result.stderr


def test_development_allows_default_secret_key():
    result = _import_security({"ENVIRONMENT": "development"})
    assert result.returncode == 0, result.stderr
