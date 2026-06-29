"""Fine-grained permissions API (T8): per-member overrides + custom presets.

The admin panel surface behind ``MEMBER_MANAGE`` (plan §2/§15.10):

* a read-only **catalog** of every permission (grouped/labelled for the UI);
* read/write of a **member's permissions** — an optional custom preset (base) and
  a ``{permission_value: bool}`` override map (grant/revoke);
* CRUD of **custom presets** (reusable named permission sets = custom roles).

Effective permissions stay computed server-side in
:func:`authz.effective_permissions` (ADMIN immune); these endpoints only persist
the inputs. Everything is tenant-scoped: a foreign id is reported as ``404``.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import update
from sqlmodel import Session, select

from auth_context import (
    AccessContext,
    find_membership,
    owned_or_404,
    preset_permission_set,
    require_permission,
)
from authz import PERMISSION_CATALOG, Permission, effective_permissions
from database import get_session
from models import Membership, PermissionPreset, Role

router = APIRouter(prefix="/api/asso/{association_id}", tags=["permissions"])

_PERMISSION_VALUES = frozenset(p.value for p in Permission)


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #
class PermissionInfoRead(BaseModel):
    value: str
    group: str
    label: str


class MemberPermissionsRead(BaseModel):
    user_id: str
    role: Role
    is_admin: bool
    preset_id: str | None
    role_permissions: list[str]  # the built-in role's set (base when no preset)
    base_permissions: list[str]  # current base (role or preset), before overrides
    overrides: dict[str, bool]
    effective: list[str]


class SetMemberPermissionsRequest(BaseModel):
    preset_id: str | None = None
    overrides: dict[str, bool] = {}


class PresetRead(BaseModel):
    id: str
    nom: str
    permissions: list[str]


class CreatePresetRequest(BaseModel):
    nom: str
    permissions: list[str] = []


class UpdatePresetRequest(BaseModel):
    nom: str | None = None
    permissions: list[str] | None = None


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _reject_unknown_permissions(values: list[str]) -> None:
    """Raise ``422`` if any value is not a known permission (``domain:action``)."""
    unknown = [v for v in values if v not in _PERMISSION_VALUES]
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Permissions inconnues : {', '.join(sorted(set(unknown)))}",
        )


def _validate_permission_values(values: list[str]) -> list[str]:
    """Canonicalize a list of permission values, or ``422`` on an unknown one."""
    _reject_unknown_permissions(values)
    # Stable order following the catalog; de-duplicated.
    seen = set(values)
    return [
        info.permission.value
        for info in PERMISSION_CATALOG
        if info.permission.value in seen
    ]


def _member_or_404(session: Session, association_id: str, user_id: str) -> Membership:
    membership = find_membership(session, association_id, user_id)
    if membership is None:
        raise HTTPException(status_code=404, detail="Member not found")
    return membership


def _member_permissions_read(
    session: Session, association_id: str, membership: Membership
) -> MemberPermissionsRead:
    # Base/role sets reuse the single engine (admin → all, preset replaces role),
    # so the admin-immunity invariant lives only in effective_permissions.
    preset_set = preset_permission_set(session, association_id, membership.preset_id)
    base_set = effective_permissions(membership.role, preset_set)
    role_set = effective_permissions(membership.role)
    effective = effective_permissions(
        membership.role, preset_set, membership.permission_overrides
    )
    return MemberPermissionsRead(
        user_id=membership.user_id,
        role=membership.role,
        is_admin=membership.role is Role.ADMIN,
        preset_id=membership.preset_id,
        role_permissions=sorted(p.value for p in role_set),
        base_permissions=sorted(p.value for p in base_set),
        overrides=dict(membership.permission_overrides),
        effective=sorted(p.value for p in effective),
    )


# --------------------------------------------------------------------------- #
# Catalog
# --------------------------------------------------------------------------- #
@router.get("/permissions/catalog", response_model=list[PermissionInfoRead])
def permission_catalog(
    ctx: AccessContext = Depends(require_permission(Permission.MEMBER_MANAGE)),
):
    return [
        PermissionInfoRead(
            value=info.permission.value, group=info.group, label=info.label
        )
        for info in PERMISSION_CATALOG
    ]


# --------------------------------------------------------------------------- #
# Member permissions
# --------------------------------------------------------------------------- #
@router.get("/members/{user_id}/permissions", response_model=MemberPermissionsRead)
def get_member_permissions(
    user_id: str,
    ctx: AccessContext = Depends(require_permission(Permission.MEMBER_MANAGE)),
    session: Session = Depends(get_session),
):
    membership = _member_or_404(session, ctx.association_id, user_id)
    return _member_permissions_read(session, ctx.association_id, membership)


@router.put("/members/{user_id}/permissions", response_model=MemberPermissionsRead)
def set_member_permissions(
    user_id: str,
    body: SetMemberPermissionsRequest,
    ctx: AccessContext = Depends(require_permission(Permission.MEMBER_MANAGE)),
    session: Session = Depends(get_session),
):
    membership = _member_or_404(session, ctx.association_id, user_id)

    # An admin is a full superset by design; restricting one is meaningless and
    # would suggest a lockout is possible. Reject editing admin permissions.
    if membership.role is Role.ADMIN:
        raise HTTPException(
            status_code=400,
            detail="Un administrateur dispose de toutes les permissions.",
        )

    # The preset, if any, must belong to this association (no existence leak).
    if body.preset_id is not None:
        owned_or_404(
            session,
            PermissionPreset,
            body.preset_id,
            ctx.association_id,
            "Preset introuvable",
        )

    # Reject unknown override keys explicitly.
    _reject_unknown_permissions(list(body.overrides))

    membership.preset_id = body.preset_id
    membership.permission_overrides = dict(body.overrides)
    session.add(membership)
    session.commit()
    session.refresh(membership)
    return _member_permissions_read(session, ctx.association_id, membership)


# --------------------------------------------------------------------------- #
# Custom presets
# --------------------------------------------------------------------------- #
@router.get("/permission-presets", response_model=list[PresetRead])
def list_presets(
    ctx: AccessContext = Depends(require_permission(Permission.MEMBER_MANAGE)),
    session: Session = Depends(get_session),
):
    presets = session.exec(
        select(PermissionPreset)
        .where(PermissionPreset.association_id == ctx.association_id)
        .order_by(PermissionPreset.nom)
    ).all()
    return [
        PresetRead(id=p.id, nom=p.nom, permissions=list(p.permissions)) for p in presets
    ]


@router.post("/permission-presets", response_model=PresetRead, status_code=201)
def create_preset(
    body: CreatePresetRequest,
    ctx: AccessContext = Depends(require_permission(Permission.MEMBER_MANAGE)),
    session: Session = Depends(get_session),
):
    nom = body.nom.strip()
    if not nom:
        raise HTTPException(status_code=400, detail="Le nom est requis.")
    permissions = _validate_permission_values(body.permissions)

    existing = session.exec(
        select(PermissionPreset).where(
            PermissionPreset.association_id == ctx.association_id,
            PermissionPreset.nom == nom,
        )
    ).first()
    if existing is not None:
        raise HTTPException(status_code=400, detail="Ce nom de preset existe déjà.")

    preset = PermissionPreset(
        association_id=ctx.association_id, nom=nom, permissions=permissions
    )
    session.add(preset)
    session.commit()
    session.refresh(preset)
    return PresetRead(
        id=preset.id, nom=preset.nom, permissions=list(preset.permissions)
    )


@router.patch("/permission-presets/{preset_id}", response_model=PresetRead)
def update_preset(
    preset_id: str,
    body: UpdatePresetRequest,
    ctx: AccessContext = Depends(require_permission(Permission.MEMBER_MANAGE)),
    session: Session = Depends(get_session),
):
    preset = owned_or_404(
        session, PermissionPreset, preset_id, ctx.association_id, "Preset introuvable"
    )

    if body.nom is not None:
        nom = body.nom.strip()
        if not nom:
            raise HTTPException(status_code=400, detail="Le nom est requis.")
        clash = session.exec(
            select(PermissionPreset).where(
                PermissionPreset.association_id == ctx.association_id,
                PermissionPreset.nom == nom,
                PermissionPreset.id != preset.id,
            )
        ).first()
        if clash is not None:
            raise HTTPException(status_code=400, detail="Ce nom de preset existe déjà.")
        preset.nom = nom

    if body.permissions is not None:
        preset.permissions = _validate_permission_values(body.permissions)

    session.add(preset)
    session.commit()
    session.refresh(preset)
    return PresetRead(
        id=preset.id, nom=preset.nom, permissions=list(preset.permissions)
    )


@router.delete("/permission-presets/{preset_id}")
def delete_preset(
    preset_id: str,
    ctx: AccessContext = Depends(require_permission(Permission.MEMBER_MANAGE)),
    session: Session = Depends(get_session),
):
    preset = owned_or_404(
        session, PermissionPreset, preset_id, ctx.association_id, "Preset introuvable"
    )
    # Detach it from any member first: they fall back to their role base.
    session.exec(
        update(Membership)
        .where(Membership.preset_id == preset.id)
        .values(preset_id=None)
    )
    session.delete(preset)
    session.commit()
    return {"message": "Preset supprimé"}
