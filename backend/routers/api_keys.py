import hashlib
import secrets

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from database import get_session
from dependencies import get_current_association
from models import ApiKey, ApiKeyCreated, ApiKeyRead, Association

router = APIRouter(prefix="/api/api-keys", tags=["api-keys"])


class CreateApiKeyRequest(BaseModel):
    name: str


def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


@router.post("", response_model=ApiKeyCreated)
def create_api_key(
    request: CreateApiKeyRequest,
    current_association: Association = Depends(get_current_association),
    session: Session = Depends(get_session),
):
    raw_key = f"abk_{secrets.token_urlsafe(32)}"
    key_hash = _hash_key(raw_key)
    key_prefix = raw_key[:8]

    api_key = ApiKey(
        name=request.name,
        key_hash=key_hash,
        key_prefix=key_prefix,
        association_id=current_association.id,
    )
    session.add(api_key)
    session.commit()
    session.refresh(api_key)

    return ApiKeyCreated(
        id=api_key.id,
        name=api_key.name,
        key=raw_key,
        key_prefix=key_prefix,
        created_at=api_key.created_at,
    )


@router.get("", response_model=list[ApiKeyRead])
def list_api_keys(
    current_association: Association = Depends(get_current_association),
    session: Session = Depends(get_session),
):
    statement = (
        select(ApiKey)
        .where(ApiKey.association_id == current_association.id)
        .order_by(ApiKey.created_at.desc())
    )
    return session.exec(statement).all()


@router.delete("/{key_id}")
def revoke_api_key(
    key_id: str,
    current_association: Association = Depends(get_current_association),
    session: Session = Depends(get_session),
):
    api_key = session.get(ApiKey, key_id)
    if not api_key or api_key.association_id != current_association.id:
        raise HTTPException(status_code=404, detail="API key not found")

    session.delete(api_key)
    session.commit()
    return {"message": "API key revoked"}
