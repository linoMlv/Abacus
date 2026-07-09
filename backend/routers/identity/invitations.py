"""Invitations: create/list/revoke (admin) and public preview/accept."""

import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlmodel import Session, select

from auth_context import (
    AccessContext,
    find_membership,
    owned_or_404,
    require_permission,
)
from authz import Permission
from database import get_session
from email_service import send_invitation_email
from models import Association, Invitation, Membership, User
from rate_limit import AUTH_RATE_LIMIT, limiter
from security import get_password_hash, hash_token

from .helpers import (
    INVITATION_EXPIRE_DAYS,
    _check_password_strength,
    _invitation_read,
    _issue_user_session,
    _normalize_email,
    _optional_current_user,
    _session_response,
    _utcnow,
)
from .schemas import (
    AcceptInvitationRequest,
    CreateInvitationRequest,
    InvitationCreated,
    InvitationPreview,
    InvitationRead,
    SessionResponse,
)

router = APIRouter(tags=["identity"])


@router.post(
    "/api/asso/{association_id}/invitations",
    response_model=InvitationCreated,
    status_code=201,
)
def create_invitation(
    request: CreateInvitationRequest,
    ctx: AccessContext = Depends(require_permission(Permission.MEMBER_MANAGE)),
    session: Session = Depends(get_session),
):
    email = _normalize_email(request.email)

    # Reject inviting someone who is already a member of this association.
    existing_user = session.exec(select(User).where(User.email == email)).first()
    if existing_user and find_membership(session, ctx.association_id, existing_user.id):
        raise HTTPException(status_code=400, detail="This person is already a member")

    # Keep a single live invitation per (association, email): drop prior ones.
    prior = session.exec(
        select(Invitation).where(
            Invitation.association_id == ctx.association_id,
            Invitation.email == email,
            Invitation.accepted_at.is_(None),
        )
    ).all()
    for old in prior:
        session.delete(old)

    raw_token = secrets.token_urlsafe(32)
    invitation = Invitation(
        association_id=ctx.association_id,
        email=email,
        role=request.role,
        token_hash=hash_token(raw_token),
        invited_by=ctx.user.id,
        expires_at=_utcnow() + timedelta(days=INVITATION_EXPIRE_DAYS),
    )
    session.add(invitation)
    session.commit()
    session.refresh(invitation)

    association = session.get(Association, ctx.association_id)
    send_invitation_email(email, association.name, raw_token)

    return InvitationCreated(
        **_invitation_read(invitation).model_dump(), token=raw_token
    )


@router.get(
    "/api/asso/{association_id}/invitations",
    response_model=list[InvitationRead],
)
def list_invitations(
    ctx: AccessContext = Depends(require_permission(Permission.MEMBER_MANAGE)),
    session: Session = Depends(get_session),
):
    invitations = session.exec(
        select(Invitation).where(
            Invitation.association_id == ctx.association_id,
            Invitation.accepted_at.is_(None),
        )
    ).all()
    return [_invitation_read(inv) for inv in invitations]


@router.delete("/api/asso/{association_id}/invitations/{invitation_id}")
def revoke_invitation(
    invitation_id: str,
    ctx: AccessContext = Depends(require_permission(Permission.MEMBER_MANAGE)),
    session: Session = Depends(get_session),
):
    # Scope check: never reveal/affect another association's invitations.
    invitation = owned_or_404(
        session, Invitation, invitation_id, ctx.association_id, "Invitation not found"
    )
    session.delete(invitation)
    session.commit()
    return {"message": "Invitation revoked"}


@router.get("/api/auth/invitations/{token}", response_model=InvitationPreview)
def preview_invitation(token: str, session: Session = Depends(get_session)):
    """Public preview of a pending invitation, keyed by its (secret) token.

    Lets the acceptance page show the association and the invited e-mail (so the
    e-mail can be pre-filled and locked) before the user signs in or registers.
    The token is the credential — no account state is revealed, and an unknown,
    expired or already-accepted invitation is a uniform ``404``.
    """
    invitation = session.exec(
        select(Invitation).where(Invitation.token_hash == hash_token(token))
    ).first()
    now = _utcnow()
    if (
        not invitation
        or invitation.accepted_at is not None
        or invitation.expires_at < now
    ):
        raise HTTPException(status_code=404, detail="Invitation invalide ou expirée")

    association = session.get(Association, invitation.association_id)
    return InvitationPreview(
        association_id=invitation.association_id,
        association_name=association.name if association else "",
        email=invitation.email,
        role=invitation.role,
    )


@router.post("/api/auth/invitations/accept", response_model=SessionResponse)
@limiter.limit(AUTH_RATE_LIMIT)
def accept_invitation(
    request: Request,
    response: Response,
    body: AcceptInvitationRequest,
    session: Session = Depends(get_session),
):
    invitation = session.exec(
        select(Invitation).where(Invitation.token_hash == hash_token(body.token))
    ).first()
    now = _utcnow()
    invalid = HTTPException(status_code=400, detail="Invalid or expired invitation")
    if (
        not invitation
        or invitation.accepted_at is not None
        or invitation.expires_at < now
    ):
        raise invalid

    email = invitation.email
    user = session.exec(select(User).where(User.email == email)).first()
    current = _optional_current_user(request, session)
    issue_session = False

    if user is not None:
        # The invitation targets an existing account; the caller must be it.
        if current is None:
            raise HTTPException(
                status_code=401,
                detail="Please log in as the invited account to accept",
            )
        if current.id != user.id:
            raise HTTPException(
                status_code=403, detail="This invitation is for another account"
            )
        acting = user
    else:
        # No account yet: create one on the fly from the invitation email.
        if not body.name or not body.password:
            raise HTTPException(
                status_code=400,
                detail="Account creation requires name and password",
            )
        _check_password_strength(body.password)
        acting = User(
            email=email,
            password=get_password_hash(body.password),
            name=body.name,
        )
        session.add(acting)
        session.commit()
        session.refresh(acting)
        issue_session = True

    if find_membership(session, invitation.association_id, acting.id) is None:
        session.add(
            Membership(
                user_id=acting.id,
                association_id=invitation.association_id,
                role=invitation.role,
                invited_by=invitation.invited_by,
            )
        )
    invitation.accepted_at = now
    session.add(invitation)
    session.commit()

    if issue_session:
        _issue_user_session(response, acting, request, session)

    return _session_response(session, acting)
