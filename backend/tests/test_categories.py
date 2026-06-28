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


def _simple_entry(admin: TestClient, assoc: str, libelle: str) -> dict:
    cat = next(
        c
        for c in admin.get(f"/api/asso/{assoc}/categories").json()
        if c["libelle"] == libelle
    )
    banque = next(
        r
        for r in admin.get(f"/api/asso/{assoc}/tresorerie").json()
        if r["numero"] == "512"
    )
    resp = admin.post(
        f"/api/asso/{assoc}/ecritures/simple",
        json={
            "categorie_id": cat["id"],
            "compte_tresorerie_id": banque["id"],
            "montant": "10.00",
            "date": "2026-06-28",
        },
    )
    assert resp.status_code == 201, resp.text
    return {"cat": cat, "entry": resp.json()}


def test_simple_entry_records_its_category():
    admin, assoc = _admin_with_association("admin@example.com", "a@example.com")
    result = _simple_entry(admin, assoc, "Cotisations")

    # The entry keeps the category used, unblocking "by category" views.
    assert result["entry"]["categorie_id"] == result["cat"]["id"]
    row = admin.get(f"/api/asso/{assoc}/ecritures").json()[0]
    assert row["categorie_id"] == result["cat"]["id"]


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


# --- CRUD (custom categories) ---------------------------------------------


def _member_client(session: Session, assoc: str, email: str, role: Role) -> TestClient:
    client = _client()
    uid = _register(client, email)
    _login(client, email)
    session.add(Membership(user_id=uid, association_id=assoc, role=role))
    session.commit()
    return client


def _numero(admin: TestClient, assoc: str, compte_id: str) -> str:
    comptes = admin.get(
        f"/api/asso/{assoc}/comptes", params={"include_inactive": True}
    ).json()
    return next(c["numero"] for c in comptes if c["id"] == compte_id)


def _journal_code(admin: TestClient, assoc: str, journal_id: str) -> str:
    return next(
        j["code"]
        for j in admin.get(f"/api/asso/{assoc}/journaux").json()
        if j["id"] == journal_id
    )


def test_create_recette_category_auto_maps_to_758_ve():
    admin, assoc = _admin_with_association("admin@example.com", "a@example.com")
    resp = admin.post(
        f"/api/asso/{assoc}/categories",
        json={"sens": "recette", "libelle": "Buvette"},
    )
    assert resp.status_code == 201, resp.text
    cat = resp.json()
    assert cat["sens"] == "recette"
    assert cat["is_active"] is True
    assert _numero(admin, assoc, cat["compte_id"]) == "758"
    assert _journal_code(admin, assoc, cat["journal_id"]) == "VE"


def test_create_depense_category_auto_maps_to_658_ac():
    admin, assoc = _admin_with_association("admin@example.com", "a@example.com")
    resp = admin.post(
        f"/api/asso/{assoc}/categories",
        json={"sens": "depense", "libelle": "Matériel sportif"},
    )
    assert resp.status_code == 201, resp.text
    cat = resp.json()
    assert _numero(admin, assoc, cat["compte_id"]) == "658"
    assert _journal_code(admin, assoc, cat["journal_id"]) == "AC"


def test_create_with_explicit_account_for_the_expert():
    admin, assoc = _admin_with_association("admin@example.com", "a@example.com")
    compte_756 = next(
        c
        for c in admin.get(f"/api/asso/{assoc}/comptes", params={"classe": 7}).json()
        if c["numero"] == "756"
    )
    resp = admin.post(
        f"/api/asso/{assoc}/categories",
        json={"sens": "recette", "libelle": "Adhésions", "compte_id": compte_756["id"]},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["compte_id"] == compte_756["id"]


def test_create_rejects_account_of_the_wrong_nature():
    admin, assoc = _admin_with_association("admin@example.com", "a@example.com")
    charge = next(
        c
        for c in admin.get(f"/api/asso/{assoc}/comptes", params={"classe": 6}).json()
        if c["numero"] == "658"
    )
    # A recette must point at a produit account, not a charge.
    resp = admin.post(
        f"/api/asso/{assoc}/categories",
        json={"sens": "recette", "libelle": "Erreur", "compte_id": charge["id"]},
    )
    assert resp.status_code == 400


def test_create_rejects_duplicate_libelle():
    admin, assoc = _admin_with_association("admin@example.com", "a@example.com")
    # "Cotisations" is seeded.
    resp = admin.post(
        f"/api/asso/{assoc}/categories",
        json={"sens": "recette", "libelle": "Cotisations"},
    )
    assert resp.status_code == 400


def test_rename_and_deactivate_category():
    admin, assoc = _admin_with_association("admin@example.com", "a@example.com")
    cat = next(
        c
        for c in admin.get(f"/api/asso/{assoc}/categories").json()
        if c["libelle"] == "Produits divers"
    )
    resp = admin.patch(
        f"/api/asso/{assoc}/categories/{cat['id']}",
        json={"libelle": "Divers recettes", "is_active": False},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["libelle"] == "Divers recettes"

    # Deactivated: gone from the default list, present with include_inactive.
    active = admin.get(f"/api/asso/{assoc}/categories").json()
    assert all(c["id"] != cat["id"] for c in active)
    full = admin.get(
        f"/api/asso/{assoc}/categories", params={"include_inactive": True}
    ).json()
    assert any(c["id"] == cat["id"] for c in full)


def test_deactivating_a_category_keeps_past_entries_valid():
    admin, assoc = _admin_with_association("admin@example.com", "a@example.com")
    result = _simple_entry(admin, assoc, "Cotisations")
    cat_id = result["cat"]["id"]
    admin.patch(f"/api/asso/{assoc}/categories/{cat_id}", json={"is_active": False})

    # The entry still lists and still references the (now inactive) category.
    row = admin.get(f"/api/asso/{assoc}/ecritures").json()[0]
    assert row["categorie_id"] == cat_id


def test_treasurer_can_quick_add_but_viewer_cannot(session: Session):
    _, assoc = _admin_with_association("admin@example.com", "a@example.com")
    treasurer = _member_client(session, assoc, "tres@example.com", Role.TREASURER)
    viewer = _member_client(session, assoc, "view@example.com", Role.VIEWER)

    assert (
        treasurer.post(
            f"/api/asso/{assoc}/categories",
            json={"sens": "depense", "libelle": "Snacks"},
        ).status_code
        == 201
    )
    assert (
        viewer.post(
            f"/api/asso/{assoc}/categories",
            json={"sens": "depense", "libelle": "Interdit"},
        ).status_code
        == 403
    )


def test_category_crud_is_tenant_isolated():
    admin_a, assoc_a = _admin_with_association("a@example.com", "aa@example.com")
    cat_a = admin_a.get(f"/api/asso/{assoc_a}/categories").json()[0]
    admin_b, assoc_b = _admin_with_association("b@example.com", "bb@example.com")

    # B cannot patch A's category through B's own scope.
    assert (
        admin_b.patch(
            f"/api/asso/{assoc_b}/categories/{cat_a['id']}", json={"libelle": "x"}
        ).status_code
        == 404
    )
