"""API keys for machine access to the MCP server (Phase 6, plan §7).

An admin (``APIKEY_MANAGE``) mints a key bound to a member of the association:
the key then acts as that member and inherits their effective permissions. This
is how MCP access is "filtered by the role of the key" — bind a key to a viewer
for a read-only assistant, to a treasurer for assisted entry, etc.

The raw ``abk_…`` secret is returned exactly once, at creation; only its SHA-256
hash is stored. Revocation is soft (the row and hash are kept for audit).
"""

import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, SQLModel, desc, select

from api_auth import API_KEY_PREFIX
from audit import AuditAction, record_audit
from auth_context import (
    AccessContext,
    find_membership,
    owned_or_404,
    require_permission,
)
from authz import Permission
from database import get_session
from models import (
    ApiKey,
    ApiKeyCreated,
    ApiKeyRead,
    Membership,
    MembershipStatus,
    User,
    utcnow,
)
from security import hash_token

router = APIRouter(prefix="/api/asso/{association_id}", tags=["api-keys"])


class CreateApiKeyRequest(SQLModel):
    name: str
    # The member the key acts as (by user id); defaults to the calling admin.
    user_id: str | None = None


def _generate_raw_key() -> str:
    """A fresh opaque secret: ``abk_`` + URL-safe randomness."""
    return f"{API_KEY_PREFIX}{secrets.token_urlsafe(32)}"


def _read(key: ApiKey, membership: Membership | None, user: User | None) -> ApiKeyRead:
    return ApiKeyRead(
        id=key.id,
        name=key.name,
        prefix=key.prefix,
        membership_id=key.membership_id,
        created_at=key.created_at,
        last_used_at=key.last_used_at,
        revoked_at=key.revoked_at,
        role=membership.role.value if membership else None,
        member_name=user.name if user else None,
        member_email=user.email if user else None,
    )


@router.get("/api-keys", response_model=list[ApiKeyRead])
def list_api_keys(
    ctx: AccessContext = Depends(require_permission(Permission.APIKEY_MANAGE)),
    session: Session = Depends(get_session),
):
    """List the association's keys (never the raw secret), most recent first."""
    rows = session.exec(
        select(ApiKey, Membership, User)
        .join(Membership, Membership.id == ApiKey.membership_id)
        .join(User, User.id == Membership.user_id)
        .where(ApiKey.association_id == ctx.association_id)
        .order_by(desc(ApiKey.created_at))
    ).all()
    return [_read(key, membership, user) for key, membership, user in rows]


@router.post(
    "/api-keys", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED
)
def create_api_key(
    body: CreateApiKeyRequest,
    ctx: AccessContext = Depends(require_permission(Permission.APIKEY_MANAGE)),
    session: Session = Depends(get_session),
):
    """Mint a key bound to a member; return the raw secret exactly once."""
    name = body.name.strip()
    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Le nom est obligatoire."
        )

    if body.user_id is None or body.user_id == ctx.user.id:
        membership = ctx.membership
    else:
        # Re-derive the target member's membership within THIS tenant only; a
        # user id from another association simply has no membership here (404).
        membership = find_membership(session, ctx.association_id, body.user_id)
        if membership is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Membre introuvable"
            )
    if membership.status != MembershipStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ce membre n'est pas actif.",
        )

    raw = _generate_raw_key()
    key = ApiKey(
        association_id=ctx.association_id,
        membership_id=membership.id,
        name=name,
        prefix=raw[:10],
        key_hash=hash_token(raw),
        created_by=ctx.user.id,
    )
    session.add(key)
    record_audit(
        session,
        association_id=ctx.association_id,
        actor_user_id=ctx.user.id,
        action=AuditAction.APIKEY_CREATE,
        target_type="api_key",
        target_id=key.id,
        detail=name,
    )
    session.commit()
    session.refresh(key)

    user = session.get(User, membership.user_id)
    read = _read(key, membership, user)
    return ApiKeyCreated(**read.model_dump(), key=raw)


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_api_key(
    key_id: str,
    ctx: AccessContext = Depends(require_permission(Permission.APIKEY_MANAGE)),
    session: Session = Depends(get_session),
):
    """Revoke a key (soft): it stops resolving immediately; the row is kept."""
    key = owned_or_404(session, ApiKey, key_id, ctx.association_id, "Clé introuvable")
    if key.revoked_at is None:
        key.revoked_at = utcnow()
        session.add(key)
        record_audit(
            session,
            association_id=ctx.association_id,
            actor_user_id=ctx.user.id,
            action=AuditAction.APIKEY_REVOKE,
            target_type="api_key",
            target_id=key.id,
            detail=key.name,
        )
        session.commit()
