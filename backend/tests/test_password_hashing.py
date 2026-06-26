"""Password hashing: argon2id, legacy-bcrypt verification, rehash and policy."""

import bcrypt
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from database import get_session
from main import _fastapi_app as app
from models import User
from security import (
    get_password_hash,
    password_needs_rehash,
    validate_password_strength,
    verify_password,
)

PASSWORD = "password123"


@pytest.fixture(autouse=True)
def _use_test_session(session: Session):
    app.dependency_overrides[get_session] = lambda: session
    yield
    app.dependency_overrides.clear()


def _legacy_bcrypt(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


# --- Hashing unit ---------------------------------------------------------


def test_new_hashes_use_argon2id():
    hashed = get_password_hash(PASSWORD)
    assert hashed.startswith("$argon2id")
    assert verify_password(PASSWORD, hashed)
    assert not verify_password("wrong", hashed)
    assert password_needs_rehash(hashed) is False


def test_legacy_bcrypt_hash_still_verifies_but_wants_rehash():
    legacy = _legacy_bcrypt(PASSWORD)
    assert verify_password(PASSWORD, legacy)
    assert not verify_password("wrong", legacy)
    # A bcrypt hash must be flagged for upgrade.
    assert password_needs_rehash(legacy) is True


def test_password_policy_rejects_short_passwords():
    with pytest.raises(ValueError, match="au moins"):
        validate_password_strength("short")  # 5 chars < 8
    # Exactly the minimum is accepted.
    validate_password_strength("12345678")


# --- Policy at account creation -------------------------------------------


def test_register_rejects_weak_password():
    client = TestClient(app)
    resp = client.post(
        "/api/auth/register",
        json={"email": "weak@example.com", "password": "short", "name": "W"},
    )
    assert resp.status_code == 400


def test_register_accepts_strong_password():
    client = TestClient(app)
    resp = client.post(
        "/api/auth/register",
        json={"email": "strong@example.com", "password": PASSWORD, "name": "S"},
    )
    assert resp.status_code == 201


# --- Transparent rehash on login ------------------------------------------


def test_login_upgrades_a_legacy_bcrypt_hash(session: Session):
    user = User(
        email="legacy@example.com", password=_legacy_bcrypt(PASSWORD), name="Legacy"
    )
    session.add(user)
    session.commit()

    client = TestClient(app)
    resp = client.post(
        "/api/auth/login", json={"email": "legacy@example.com", "password": PASSWORD}
    )
    assert resp.status_code == 200, resp.text

    stored = session.exec(
        select(User).where(User.email == "legacy@example.com")
    ).first()
    # The hash has been upgraded to argon2id in place.
    assert stored.password.startswith("$argon2id")
    # And the new hash still authenticates the same password.
    assert verify_password(PASSWORD, stored.password)
