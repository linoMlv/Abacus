"""Assisted-entry categories: seeding, mapping, read endpoint and isolation."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from accounting_seed import DEFAULT_CATEGORIES, seed_association_accounting
from database import get_session
from main import _fastapi_app as app
from models import Association, CategorieSaisie, Compte, Journal, Membership, Role

PASSWORD = "password123"


@pytest.fixture(autouse=True)
def _use_test_session(session: Session):
    app.dependency_overrides[get_session] = lambda: session
    yield
    app.dependency_overrides.clear()


def _client() -> TestClient:
    return TestClient(app)


def _register(client: TestClient, email: str) -> str:
    resp = client.post(
        "/api/auth/register",
        json={"email": email, "password": PASSWORD, "name": "User"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _login(client: TestClient, email: str) -> None:
    assert (
        client.post(
            "/api/auth/login", json={"email": email, "password": PASSWORD}
        ).status_code
        == 200
    )


def _admin_with_association(email: str, assoc_email: str) -> tuple[TestClient, str]:
    client = _client()
    _register(client, email)
    _login(client, email)
    resp = client.post(
        "/api/auth/associations",
        json={"name": assoc_email.split("@")[0], "email": assoc_email},
    )
    assert resp.status_code == 201, resp.text
    return client, resp.json()["id"]


# --- Seeding & mapping ----------------------------------------------------


def test_seed_creates_categories_mapped_to_real_accounts(session: Session):
    association = Association(name="A", email="a@example.com", password="x")
    session.add(association)
    session.flush()
    seed_association_accounting(session, association.id)
    session.commit()

    categories = session.exec(
        select(CategorieSaisie).where(CategorieSaisie.association_id == association.id)
    ).all()
    assert len(categories) == len(DEFAULT_CATEGORIES)

    numero_by_id = {
        c.id: c.numero
        for c in session.exec(
            select(Compte).where(Compte.association_id == association.id)
        ).all()
    }
    code_by_journal = {
        j.id: j.code
        for j in session.exec(
            select(Journal).where(Journal.association_id == association.id)
        ).all()
    }
    # Every category points at an account and journal of the same association,
    # matching the declared mapping.
    by_libelle = {c.libelle: c for c in categories}
    for sens, libelle, numero, code in DEFAULT_CATEGORIES:
        cat = by_libelle[libelle]
        assert cat.sens == sens
        assert numero_by_id[cat.compte_id] == numero
        assert code_by_journal[cat.journal_id] == code


def test_seed_orders_inserts_under_foreign_key_enforcement():
    """Regression: the seed must insert comptes/journaux before the
    categorie_saisie rows that reference them.

    A bare FK column does not order the unit-of-work flush, so on a FK-enforcing
    backend (PostgreSQL in production) the categories could be inserted first,
    breaking association creation with a ForeignKeyViolation. SQLite leaves FKs
    unenforced by default; we turn them on here to reproduce that production
    failure locally and guard against regression.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enforce_foreign_keys(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        association = Association(name="A", email="fk@example.com", password="x")
        session.add(association)
        session.flush()

        # Without the ordering fix this commit raises IntegrityError.
        seed_association_accounting(session, association.id)
        session.commit()

        categories = session.exec(
            select(CategorieSaisie).where(
                CategorieSaisie.association_id == association.id
            )
        ).all()
    assert len(categories) == len(DEFAULT_CATEGORIES)


# --- Read endpoint --------------------------------------------------------


def test_member_lists_categories_ordered():
    admin, assoc_id = _admin_with_association("admin@example.com", "a@example.com")

    resp = admin.get(f"/api/asso/{assoc_id}/categories")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == len(DEFAULT_CATEGORIES)
    ordres = [c["ordre"] for c in body]
    assert ordres == sorted(ordres)


def test_categories_filtered_by_sens():
    admin, assoc_id = _admin_with_association("admin@example.com", "a@example.com")

    recettes = admin.get(
        f"/api/asso/{assoc_id}/categories", params={"sens": "recette"}
    ).json()
    assert recettes
    assert all(c["sens"] == "recette" for c in recettes)
    assert "Cotisations" in {c["libelle"] for c in recettes}


def test_non_member_cannot_read_categories():
    admin_a, _ = _admin_with_association("a@example.com", "aa@example.com")
    _, assoc_b = _admin_with_association("b@example.com", "bb@example.com")

    assert admin_a.get(f"/api/asso/{assoc_b}/categories").status_code == 404


def test_viewer_can_read_categories(session: Session):
    _, assoc_id = _admin_with_association("admin@example.com", "a@example.com")
    viewer = _client()
    viewer_id = _register(viewer, "viewer@example.com")
    _login(viewer, "viewer@example.com")
    session.add(
        Membership(user_id=viewer_id, association_id=assoc_id, role=Role.VIEWER)
    )
    session.commit()

    assert viewer.get(f"/api/asso/{assoc_id}/categories").status_code == 200
