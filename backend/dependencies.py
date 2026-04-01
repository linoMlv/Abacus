import hashlib
from datetime import UTC, datetime

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlmodel import Session, select
from sqlalchemy.orm import selectinload

from database import get_session
from models import ApiKey, Association
from security import ALGORITHM, SECRET_KEY

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/login", auto_error=False)


async def get_token(request: Request, token: str | None = Depends(oauth2_scheme)):
    if token:
        return token
    token = request.cookies.get("access_token")
    if token:
        if token.startswith("Bearer "):
            return token.split(" ")[1]
        return token
    return None


async def get_current_association(
    request: Request,
    token: str | None = Depends(get_token),
    session: Session = Depends(get_session),
):
    # Try API key auth first (X-API-Key header)
    api_key_header = request.headers.get("x-api-key")
    if api_key_header:
        return _authenticate_api_key(api_key_header, session)

    # Fall back to JWT auth
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        name: str = payload.get("sub")
        if name is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    statement = (
        select(Association)
        .where(Association.name == name)
        .options(selectinload(Association.balances))
    )
    association = session.exec(statement).first()
    if association is None:
        raise credentials_exception
    return association


def _authenticate_api_key(raw_key: str, session: Session) -> Association:
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    statement = (
        select(ApiKey)
        .where(ApiKey.key_hash == key_hash, ApiKey.is_active == True)
    )
    api_key = session.exec(statement).first()
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    # Update last_used_at
    api_key.last_used_at = datetime.now(UTC)
    session.add(api_key)
    session.commit()

    statement = (
        select(Association)
        .where(Association.id == api_key.association_id)
        .options(selectinload(Association.balances))
    )
    association = session.exec(statement).first()
    if not association:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Association not found",
        )
    return association
