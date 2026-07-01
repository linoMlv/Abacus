"""Request/response bodies for the identity & access API."""

from datetime import datetime

from pydantic import BaseModel

from models import MembershipStatus, Role


class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


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
    # The caller's server-authoritative effective permissions in this association
    # (role/preset base ± overrides; ADMIN = all). The UI gates on these.
    permissions: list[str]


class MemberRead(BaseModel):
    user_id: str
    email: str
    name: str
    role: Role
    status: MembershipStatus


class UpdateMemberRequest(BaseModel):
    role: Role | None = None
    status: MembershipStatus | None = None


class CreateInvitationRequest(BaseModel):
    email: str
    role: Role


class InvitationRead(BaseModel):
    id: str
    email: str
    role: Role
    created_at: datetime
    expires_at: datetime
    accepted_at: datetime | None


class InvitationCreated(InvitationRead):
    # The raw token is returned once, to the inviting admin, so a link can be
    # shared directly in addition to the e-mail.
    token: str


class AcceptInvitationRequest(BaseModel):
    token: str
    name: str | None = None
    password: str | None = None


class InvitationPreview(BaseModel):
    association_id: str
    association_name: str
    email: str
    role: Role
