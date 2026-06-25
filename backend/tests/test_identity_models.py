"""Schema-level invariants of the identity & access model.

Verifies the database constraints that underpin tenant isolation: globally
unique user identity, one membership (one role) per user-and-association, and
the explicit support for a user belonging to several associations.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from models import (
    Association,
    Invitation,
    Membership,
    MembershipStatus,
    Role,
    User,
)


def _make_association(session: Session, suffix: str) -> Association:
    assoc = Association(
        name=f"Asso {suffix}",
        email=f"contact+{suffix}@example.com",
        password="hashed",
    )
    session.add(assoc)
    session.commit()
    session.refresh(assoc)
    return assoc


def _make_user(session: Session, email: str) -> User:
    user = User(email=email, password="hashed", name="Member")
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_user_email_is_unique(session: Session):
    _make_user(session, "dup@example.com")
    session.add(User(email="dup@example.com", password="x", name="Other"))
    with pytest.raises(IntegrityError):
        session.commit()


def test_membership_is_unique_per_user_and_association(session: Session):
    assoc = _make_association(session, "a")
    user = _make_user(session, "u@example.com")

    session.add(
        Membership(user_id=user.id, association_id=assoc.id, role=Role.TREASURER)
    )
    session.commit()

    session.add(Membership(user_id=user.id, association_id=assoc.id, role=Role.ADMIN))
    with pytest.raises(IntegrityError):
        session.commit()


def test_user_can_belong_to_several_associations_with_different_roles(
    session: Session,
):
    user = _make_user(session, "multi@example.com")
    assoc_a = _make_association(session, "a")
    assoc_b = _make_association(session, "b")

    session.add(Membership(user_id=user.id, association_id=assoc_a.id, role=Role.ADMIN))
    session.add(
        Membership(user_id=user.id, association_id=assoc_b.id, role=Role.VIEWER)
    )
    session.commit()  # must NOT raise: this is the core multi-tenant requirement

    memberships = session.exec(
        select(Membership).where(Membership.user_id == user.id)
    ).all()
    roles = {m.association_id: m.role for m in memberships}
    assert roles == {assoc_a.id: Role.ADMIN, assoc_b.id: Role.VIEWER}


def test_membership_status_defaults_to_active(session: Session):
    assoc = _make_association(session, "a")
    user = _make_user(session, "u@example.com")
    membership = Membership(user_id=user.id, association_id=assoc.id, role=Role.VIEWER)
    session.add(membership)
    session.commit()
    session.refresh(membership)
    assert membership.status is MembershipStatus.ACTIVE


def test_invitation_token_hash_is_unique(session: Session):
    assoc = _make_association(session, "a")
    inviter = _make_user(session, "admin@example.com")
    expires = datetime.now(UTC) + timedelta(days=7)

    session.add(
        Invitation(
            association_id=assoc.id,
            email="invitee@example.com",
            role=Role.TREASURER,
            token_hash="same-hash",
            invited_by=inviter.id,
            expires_at=expires,
        )
    )
    session.commit()

    session.add(
        Invitation(
            association_id=assoc.id,
            email="other@example.com",
            role=Role.VIEWER,
            token_hash="same-hash",
            invited_by=inviter.id,
            expires_at=expires,
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
