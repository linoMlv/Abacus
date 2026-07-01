"""Membership management (``/api/asso/{id}/members``)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from auth_context import AccessContext, find_membership, require_permission
from authz import Permission
from database import get_session
from models import Membership, MembershipStatus, Role, User

from .helpers import _is_last_active_admin
from .schemas import MemberRead, UpdateMemberRequest

router = APIRouter(tags=["identity"])


@router.get("/api/asso/{association_id}/members", response_model=list[MemberRead])
def list_members(
    ctx: AccessContext = Depends(require_permission(Permission.MEMBER_MANAGE)),
    session: Session = Depends(get_session),
):
    rows = session.exec(
        select(Membership, User)
        .join(User, User.id == Membership.user_id)
        .where(Membership.association_id == ctx.association_id)
    ).all()
    return [
        MemberRead(
            user_id=user.id,
            email=user.email,
            name=user.name,
            role=m.role,
            status=m.status,
        )
        for m, user in rows
    ]


@router.patch("/api/asso/{association_id}/members/{user_id}", response_model=MemberRead)
def update_member(
    user_id: str,
    request: UpdateMemberRequest,
    ctx: AccessContext = Depends(require_permission(Permission.MEMBER_MANAGE)),
    session: Session = Depends(get_session),
):
    membership = find_membership(session, ctx.association_id, user_id)
    if membership is None:
        raise HTTPException(status_code=404, detail="Member not found")

    new_role = request.role if request.role is not None else membership.role
    new_status = request.status if request.status is not None else membership.status

    # Never strand an association without an administrator.
    leaves_admin = new_role != Role.ADMIN or new_status != MembershipStatus.ACTIVE
    if leaves_admin and _is_last_active_admin(session, membership):
        raise HTTPException(
            status_code=400, detail="Cannot remove the last administrator"
        )

    membership.role = new_role
    membership.status = new_status
    session.add(membership)
    session.commit()
    session.refresh(membership)

    user = session.get(User, user_id)
    return MemberRead(
        user_id=user.id,
        email=user.email,
        name=user.name,
        role=membership.role,
        status=membership.status,
    )


@router.delete("/api/asso/{association_id}/members/{user_id}")
def remove_member(
    user_id: str,
    ctx: AccessContext = Depends(require_permission(Permission.MEMBER_MANAGE)),
    session: Session = Depends(get_session),
):
    membership = find_membership(session, ctx.association_id, user_id)
    if membership is None:
        raise HTTPException(status_code=404, detail="Member not found")

    if _is_last_active_admin(session, membership):
        raise HTTPException(
            status_code=400, detail="Cannot remove the last administrator"
        )

    session.delete(membership)
    session.commit()
    return {"message": "Member removed"}
