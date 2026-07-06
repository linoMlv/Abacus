"""Machine authentication for the MCP server (Phase 6, plan §7).

An ``X-API-Key`` header identifies a :class:`~models.ApiKey`, which is bound to a
``Membership``. This module resolves a raw key into the very same
:class:`~auth_context.AccessContext` a browser request produces — so every
tenant-scoped service (synthèse, écritures, exports…) is reused unchanged, with
the key's *effective* permissions computed live.

Security rules (keep them true):

* The raw key is never stored; lookup is by SHA-256 hash only.
* A revoked key, or a key whose membership is missing/suspended, resolves to
  ``None`` (no access) — authority is never frozen into the key.
* Permissions are recomputed on every call from the membership's current
  role/preset/overrides (zero-trust; the key carries no cached grant).
"""

from sqlmodel import Session, select

from auth_context import AccessContext, _resolve_permissions
from models import ApiKey, Membership, MembershipStatus, User, utcnow
from security import hash_token

API_KEY_HEADER = "X-API-Key"
API_KEY_PREFIX = "abk_"


def resolve_api_key(session: Session, raw_key: str | None) -> AccessContext | None:
    """Resolve an ``abk_…`` key into an :class:`AccessContext`, or ``None``.

    Returns ``None`` for anything that must not grant access: absent/garbage key,
    unknown or revoked key, a membership that is missing, suspended, or whose
    user is inactive. On success the key's ``last_used_at`` is stamped.
    """
    if not raw_key or not raw_key.startswith(API_KEY_PREFIX):
        return None

    key = session.exec(
        select(ApiKey).where(ApiKey.key_hash == hash_token(raw_key))
    ).first()
    if key is None or key.revoked_at is not None:
        return None

    membership = session.get(Membership, key.membership_id)
    if membership is None or membership.status != MembershipStatus.ACTIVE:
        return None
    # Defense in depth: the membership must still belong to the key's tenant.
    if membership.association_id != key.association_id:
        return None

    user = session.get(User, membership.user_id)
    if user is None or not user.is_active:
        return None

    key.last_used_at = utcnow()
    session.add(key)
    session.commit()

    return AccessContext(
        user=user,
        association_id=membership.association_id,
        role=membership.role,
        membership=membership,
        permissions=_resolve_permissions(
            session, membership, membership.association_id
        ),
    )
