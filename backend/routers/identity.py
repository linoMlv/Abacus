"""V3 identity & access API: user accounts, associations, memberships.

Namespaced apart from the legacy association-login endpoints during the
strangler migration:

* ``/api/auth/*``           — user account & session.
* ``/api/asso/{id}/*``      — association-scoped access (URL scoping), guarded
                              by :func:`auth_context.get_active_membership`.
"""

import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlmodel import Session, select

from auth_context import (
    USER_TOKEN_TYPE,
    AccessContext,
    get_active_membership,
    get_current_user,
    require_permission,
)
from authz import Permission
from database import get_session
from models import Association, Membership, MembershipStatus, Role, User
from rate_limit import AUTH_RATE_LIMIT, limiter
from security import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    COOKIE_SECURE,
    create_access_token,
    get_password_hash,
    verify_password,
)

ACCESS_COOKIE = "access_token"
COOKIE_PATH = "/api"

router = APIRouter(tags=["identity"])


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #
class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str


class LoginRequest(BaseModel):
    email: str
    password: str


class UserRead(BaseModel):
    id: str
    email: str
    name: str


class AssociationSummary(BaseModel):
    id: str
    name: str
    role: Role
    status: MembershipStatus


class SessionResponse(BaseModel):
    user: UserRead
    associations: list[AssociationSummary]


class CreateAssociationRequest(BaseModel):
    name: str
    email: str


class AssociationContext(BaseModel):
    id: str
    name: str
    role: Role


class MemberRead(BaseModel):
    user_id: str
    email: str
    name: str
    role: Role
    status: MembershipStatus


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _issue_access_cookie(response: Response, user: User) -> str:
    token = create_access_token(
        data={"sub": user.id, "type": USER_TOKEN_TYPE},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    response.set_cookie(
        key=ACCESS_COOKIE,
        value=f"Bearer {token}",
        httponly=True,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax",
        secure=COOKIE_SECURE,
        path=COOKIE_PATH,
    )
    return token


def _associations_for(session: Session, user: User) -> list[AssociationSummary]:
    rows = session.exec(
        select(Membership, Association)
        .join(Association, Association.id == Membership.association_id)
        .where(Membership.user_id == user.id)
    ).all()
    return [
        AssociationSummary(id=assoc.id, name=assoc.name, role=m.role, status=m.status)
        for m, assoc in rows
    ]


# --------------------------------------------------------------------------- #
# Account & session
# --------------------------------------------------------------------------- #
@router.post("/api/auth/register", response_model=UserRead, status_code=201)
def register(request: RegisterRequest, session: Session = Depends(get_session)):
    email = _normalize_email(request.email)
    existing = session.exec(select(User).where(User.email == email)).first()
    if existing:
        # Generic message: do not confirm which emails are registered.
        raise HTTPException(status_code=400, detail="Unable to register")

    user = User(
        email=email,
        password=get_password_hash(request.password),
        name=request.name,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return UserRead(id=user.id, email=user.email, name=user.name)


@router.post("/api/auth/login", response_model=SessionResponse)
@limiter.limit(AUTH_RATE_LIMIT)
def login(
    request: Request,
    response: Response,
    credentials: LoginRequest,
    session: Session = Depends(get_session),
):
    email = _normalize_email(credentials.email)
    user = session.exec(select(User).where(User.email == email)).first()
    if not user or not verify_password(credentials.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    _issue_access_cookie(response, user)
    return SessionResponse(
        user=UserRead(id=user.id, email=user.email, name=user.name),
        associations=_associations_for(session, user),
    )


@router.post("/api/auth/logout")
def logout(response: Response):
    response.delete_cookie(ACCESS_COOKIE, path=COOKIE_PATH)
    return {"message": "Logged out"}


@router.get("/api/auth/session", response_model=SessionResponse)
def session_info(
    user: User = Depends(get_current_user), session: Session = Depends(get_session)
):
    return SessionResponse(
        user=UserRead(id=user.id, email=user.email, name=user.name),
        associations=_associations_for(session, user),
    )


# --------------------------------------------------------------------------- #
# Associations
# --------------------------------------------------------------------------- #
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
    session.commit()

    return AssociationSummary(
        id=association.id,
        name=association.name,
        role=membership.role,
        status=membership.status,
    )


@router.get("/api/asso/{association_id}", response_model=AssociationContext)
def association_context(
    ctx: AccessContext = Depends(get_active_membership),
    session: Session = Depends(get_session),
):
    association = session.get(Association, ctx.association_id)
    # An active membership guarantees the association exists.
    return AssociationContext(id=association.id, name=association.name, role=ctx.role)


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
