import hashlib
import os
import secrets
from datetime import UTC, datetime, timedelta

import bcrypt
from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error
from jose import jwt

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
DEFAULT_SECRET_KEY = "default_insecure_key_for_dev_only"
SECRET_KEY = os.getenv("SECRET_KEY", DEFAULT_SECRET_KEY)
if ENVIRONMENT == "production" and SECRET_KEY == DEFAULT_SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY must be set to a secure random value in production; "
        "refusing to start with the insecure default."
    )

ALGORITHM = os.getenv("ALGORITHM", "HS256")
# Short-lived access token, refreshed silently via the refresh session.
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30"))
COOKIE_SECURE = ENVIRONMENT == "production"


# Password hashing: argon2id for new hashes, with transparent verification of
# legacy bcrypt hashes so existing accounts keep working and are upgraded on
# their next successful login (see ``password_needs_rehash``).
_password_hasher = PasswordHasher()

# Minimum password length enforced at account creation / password change.
MIN_PASSWORD_LENGTH = 8


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against an argon2id *or* legacy bcrypt hash."""
    if hashed_password.startswith("$argon2"):
        try:
            return _password_hasher.verify(hashed_password, plain_password)
        except Argon2Error:
            return False
    # Legacy bcrypt hash.
    password_bytes = plain_password.encode("utf-8")[:72]
    hashed_bytes = hashed_password.encode("utf-8")
    try:
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except ValueError:
        return False


def get_password_hash(password: str) -> str:
    """Hash a password using argon2id."""
    return _password_hasher.hash(password)


def password_needs_rehash(hashed_password: str) -> bool:
    """True if ``hashed_password`` should be re-hashed (legacy or outdated params).

    Call after a successful :func:`verify_password` to transparently upgrade a
    stored hash to the current argon2id parameters.
    """
    if not hashed_password.startswith("$argon2"):
        return True
    try:
        return _password_hasher.check_needs_rehash(hashed_password)
    except Argon2Error:
        return True


def validate_password_strength(password: str) -> None:
    """Enforce the password policy. Raises ``ValueError`` if too weak."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(
            f"Le mot de passe doit contenir au moins {MIN_PASSWORD_LENGTH} caractères."
        )


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def generate_refresh_token() -> str:
    """Return a new opaque refresh token (stored only as a hash server-side)."""
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    """Hash an opaque token (refresh / invitation / API key) for storage/lookup."""
    return hashlib.sha256(token.encode()).hexdigest()


def hash_refresh_token(token: str) -> str:
    """Hash a refresh token. Alias of :func:`hash_token` for refresh call sites."""
    return hash_token(token)
