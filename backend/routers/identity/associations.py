"""Association listing, creation and context (``/api/auth/associations``,
``/api/asso/{id}``).
"""

import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from accounting_seed import seed_association_accounting
from auth_context import (
    AccessContext,
    get_active_membership,
    get_current_user,
    require_permission,
)
from authz import Permission
from database import get_session
from models import Association, Membership, Role, User
from security import get_password_hash

from .helpers import _associations_for, _normalize_email
from .schemas import (
    AssociationContext,
    AssociationSettings,
    AssociationSummary,
    CreateAssociationRequest,
    UpdateAssociationRequest,
)

router = APIRouter(tags=["identity"])


@router.get("/api/auth/associations", response_model=list[AssociationSummary])
def my_associations(
    user: User = Depends(get_current_user), session: Session = Depends(get_session)
):
    return _associations_for(session, user)


@router.post(
    "/api/auth/associations", response_model=AssociationSummary, status_code=201
)
def create_association(
    request: CreateAssociationRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    if session.exec(
        select(Association).where(Association.name == request.name)
    ).first():
        raise HTTPException(status_code=400, detail="Association name already taken")

    email = _normalize_email(request.email)
    if session.exec(select(Association).where(Association.email == email)).first():
        raise HTTPException(status_code=400, detail="Email already in use")

    association = Association(
        name=request.name,
        email=email,
        # V3 associations have no login of their own; store an unusable secret
        # so the legacy association-login path can never authenticate them.
        password=get_password_hash(secrets.token_urlsafe(32)),
    )
    session.add(association)
    session.commit()
    session.refresh(association)

    membership = Membership(
        user_id=user.id, association_id=association.id, role=Role.ADMIN
    )
    session.add(membership)
    # Seed the default chart of accounts, journals and current fiscal year.
    seed_association_accounting(session, association.id)
    session.commit()

    return AssociationSummary(
        id=association.id,
        name=association.name,
        role=membership.role,
        status=membership.status,
    )


def _context(association: Association, ctx: AccessContext) -> AssociationContext:
    return AssociationContext(
        id=association.id,
        name=association.name,
        role=ctx.role,
        regime_tva=association.regime_tva,
        permissions=sorted(p.value for p in ctx.permissions),
    )


@router.get("/api/asso/{association_id}", response_model=AssociationContext)
def association_context(
    ctx: AccessContext = Depends(get_active_membership),
    session: Session = Depends(get_session),
):
    association = session.get(Association, ctx.association_id)
    # An active membership guarantees the association exists.
    return _context(association, ctx)


_FISCAL_FIELDS = ("adresse", "code_postal", "ville", "rna", "siret", "objet")


def _settings(association: Association) -> AssociationSettings:
    return AssociationSettings(
        regime_tva=association.regime_tva,
        **{field: getattr(association, field) for field in _FISCAL_FIELDS},
    )


@router.get("/api/asso/{association_id}/parametres", response_model=AssociationSettings)
def association_settings(
    ctx: AccessContext = Depends(require_permission(Permission.SETTINGS_MANAGE)),
    session: Session = Depends(get_session),
):
    """Full settings incl. fiscal identity (durable → admin, §2)."""
    return _settings(session.get(Association, ctx.association_id))


@router.patch("/api/asso/{association_id}", response_model=AssociationContext)
def update_association(
    body: UpdateAssociationRequest,
    ctx: AccessContext = Depends(require_permission(Permission.SETTINGS_MANAGE)),
    session: Session = Depends(get_session),
):
    """Update editable association settings (durable → admin, §2)."""
    association = session.get(Association, ctx.association_id)
    if body.regime_tva is not None:
        association.regime_tva = body.regime_tva
    # Present-and-null clears a fiscal field; empty string is normalised to null.
    for field in _FISCAL_FIELDS:
        if field in body.model_fields_set:
            value = getattr(body, field)
            setattr(association, field, (value or "").strip() or None)
    session.add(association)
    session.commit()
    session.refresh(association)
    return _context(association, ctx)
