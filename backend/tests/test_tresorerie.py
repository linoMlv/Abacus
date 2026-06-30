"""Treasury accounts: seeding, model metadata, CRUD endpoints, balances.

A treasury account is a class-5 ``Compte`` carrying a ``type_tresorerie`` (§15.4):
ordinary chart-of-accounts lines leave it null. The seed marks the generic
512/531 as the association's starting bank/cash accounts so the app works out of
the box; users rename them, set opening balances and add more.
"""

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from accounting_seed import seed_association_accounting
from database import get_session
from main import _fastapi_app as app
from models import Association, Compte, Membership, Role, TypeTresorerie

PASSWORD = "password123"
TODAY = "2026-06-28"


def _seeded_association(session: Session) -> str:
    association = Association(name="Seed", email="seed@example.com", password="x")
    session.add(association)
    session.flush()
    seed_association_accounting(session, association.id, year=date.today().year)
    session.commit()
    return association.id


def test_seed_marks_bank_and_cash_as_treasury_accounts(session: Session):
    assoc_id = _seeded_association(session)
    comptes = session.exec(
        select(Compte).where(
            Compte.association_id == assoc_id,
            Compte.type_tresorerie.is_not(None),
        )
    ).all()

    by_numero = {c.numero: c for c in comptes}
    assert set(by_numero) == {"512", "531"}
    assert by_numero["512"].type_tresorerie == TypeTresorerie.BANQUE
    assert by_numero["531"].type_tresorerie == TypeTresorerie.CAISSE
    # They are ordered for display and stay normal class-5 accounts.
    assert by_numero["512"].classe == 5
    assert by_numero["512"].ordre < by_numero["531"].ordre


def test_ordinary_accounts_have_no_treasury_type(session: Session):
    assoc_id = _seeded_association(session)
    # A produit/charge account is not a treasury account.
    cotisations = session.exec(
        select(Compte).where(Compte.association_id == assoc_id, Compte.numero == "756")
    ).first()
    assert cotisations is not None
    assert cotisations.type_tresorerie is None


def test_treasury_metadata_persists(session: Session):
    assoc_id = _seeded_association(session)
    compte = Compte(
        association_id=assoc_id,
        numero="5121",
        libelle="Compte courant Crédit Agricole",
        classe=5,
        type="actif",
        type_tresorerie=TypeTresorerie.BANQUE,
        iban="FR7612345678901234567890123",
        couleur="#2563EB",
        ordre=2,
    )
    session.add(compte)
    session.commit()
    session.refresh(compte)

    reloaded = session.get(Compte, compte.id)
    assert reloaded.iban == "FR7612345678901234567890123"
    assert reloaded.couleur == "#2563EB"
    assert reloaded.ordre == 2
    assert reloaded.type_tresorerie == TypeTresorerie.BANQUE


# --- API: endpoints, balances, RBAC and isolation -------------------------


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


def _admin_with_association(email: str, name: str) -> tuple[TestClient, str]:
    client = _client()
    _register(client, email)
    _login(client, email)
    resp = client.post(
        "/api/auth/associations", json={"name": name, "email": f"{name}@example.com"}
    )
    assert resp.status_code == 201, resp.text
    return client, resp.json()["id"]


def _member_client(
    session: Session, assoc_id: str, email: str, role: Role
) -> TestClient:
    client = _client()
    uid = _register(client, email)
    _login(client, email)
    session.add(Membership(user_id=uid, association_id=assoc_id, role=role))
    session.commit()
    return client


def _dec(value) -> Decimal:
    return Decimal(str(value))


def test_seed_exposes_default_treasury_accounts():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    rows = admin.get(f"/api/asso/{assoc}/tresorerie").json()

    by_numero = {r["numero"]: r for r in rows}
    assert set(by_numero) == {"512", "531"}
    assert by_numero["512"]["type_tresorerie"] == "banque"
    assert by_numero["531"]["type_tresorerie"] == "caisse"
    assert all(_dec(r["solde"]) == Decimal("0") for r in rows)


def test_create_bank_account_gets_a_sub_number():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    resp = admin.post(
        f"/api/asso/{assoc}/tresorerie",
        json={"nom": "Compte courant CA", "type_tresorerie": "banque"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["numero"] == "5121"  # 512 is the seeded generic, so next free
    assert body["libelle"] == "Compte courant CA"
    assert body["type_tresorerie"] == "banque"
    assert _dec(body["solde"]) == Decimal("0")


def test_create_cash_account_uses_531_prefix():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    resp = admin.post(
        f"/api/asso/{assoc}/tresorerie",
        json={"nom": "Caisse buvette", "type_tresorerie": "caisse"},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["numero"] == "5311"


def test_create_online_account_uses_512_prefix():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    resp = admin.post(
        f"/api/asso/{assoc}/tresorerie",
        json={"nom": "HelloAsso", "type_tresorerie": "en_ligne"},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["numero"] == "5121"


def test_opening_balance_posts_an_a_nouveau_entry():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    resp = admin.post(
        f"/api/asso/{assoc}/tresorerie",
        json={
            "nom": "Livret",
            "type_tresorerie": "epargne",
            "solde_initial": "500.00",
            "date_solde_initial": TODAY,
        },
    )
    assert resp.status_code == 201, resp.text
    compte = resp.json()
    assert _dec(compte["solde"]) == Decimal("500.00")

    rows = admin.get(f"/api/asso/{assoc}/tresorerie").json()
    livret = next(r for r in rows if r["numero"] == compte["numero"])
    assert _dec(livret["solde"]) == Decimal("500.00")

    entries = admin.get(f"/api/asso/{assoc}/ecritures").json()
    an = [e for e in entries if e["origine"] == "a_nouveau"]
    assert len(an) == 1
    assert an[0]["journal_code"] == "OD"
    assert _dec(an[0]["montant"]) == Decimal("500.00")

    balance = admin.get(f"/api/asso/{assoc}/balance").json()
    report = next(r for r in balance if r["numero"] == "110")
    assert _dec(report["solde"]) == Decimal("-500.00")


def test_solde_reflects_a_recette_on_the_account():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    banque = next(
        r
        for r in admin.get(f"/api/asso/{assoc}/tresorerie").json()
        if r["numero"] == "512"
    )
    cats = admin.get(f"/api/asso/{assoc}/categories").json()
    cotis = next(c for c in cats if c["libelle"] == "Cotisations")
    created = admin.post(
        f"/api/asso/{assoc}/ecritures/simple",
        json={
            "categorie_id": cotis["id"],
            "compte_tresorerie_id": banque["id"],
            "montant": "150.00",
            "date": TODAY,
        },
    ).json()
    # Only validated entries move the (official) treasury solde.
    admin.post(f"/api/asso/{assoc}/ecritures/{created['id']}/validation")

    rows = admin.get(f"/api/asso/{assoc}/tresorerie").json()
    solde = _dec(next(r for r in rows if r["numero"] == "512")["solde"])
    assert solde == Decimal("150.00")


def test_update_renames_recolours_and_archives():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    caisse = next(
        r
        for r in admin.get(f"/api/asso/{assoc}/tresorerie").json()
        if r["numero"] == "531"
    )
    resp = admin.patch(
        f"/api/asso/{assoc}/tresorerie/{caisse['id']}",
        json={"nom": "Caisse principale", "couleur": "#16A34A", "is_active": False},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["libelle"] == "Caisse principale"
    assert resp.json()["couleur"] == "#16A34A"

    active = admin.get(f"/api/asso/{assoc}/tresorerie").json()
    assert all(r["numero"] != "531" for r in active)
    full = admin.get(
        f"/api/asso/{assoc}/tresorerie", params={"include_inactive": True}
    ).json()
    assert any(r["numero"] == "531" for r in full)


def test_patch_on_ordinary_account_is_404(session: Session):
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    cotis = session.exec(
        select(Compte).where(Compte.association_id == assoc, Compte.numero == "756")
    ).first()
    resp = admin.patch(f"/api/asso/{assoc}/tresorerie/{cotis.id}", json={"nom": "Hack"})
    assert resp.status_code == 404


def test_treasurer_can_create_but_viewer_cannot(session: Session):
    _, assoc = _admin_with_association("admin@example.com", "alpha")
    treasurer = _member_client(session, assoc, "tres@example.com", Role.TREASURER)
    viewer = _member_client(session, assoc, "view@example.com", Role.VIEWER)

    assert (
        treasurer.post(
            f"/api/asso/{assoc}/tresorerie",
            json={"nom": "Caisse événement", "type_tresorerie": "caisse"},
        ).status_code
        == 201
    )
    assert (
        viewer.post(
            f"/api/asso/{assoc}/tresorerie",
            json={"nom": "Interdit", "type_tresorerie": "banque"},
        ).status_code
        == 403
    )


def test_treasury_is_tenant_isolated():
    admin_a, assoc_a = _admin_with_association("a@example.com", "alpha")
    bank_a = next(
        r
        for r in admin_a.get(f"/api/asso/{assoc_a}/tresorerie").json()
        if r["numero"] == "512"
    )
    admin_b, assoc_b = _admin_with_association("b@example.com", "beta")

    assert admin_b.get(f"/api/asso/{assoc_a}/tresorerie").status_code == 404
    assert (
        admin_b.patch(
            f"/api/asso/{assoc_b}/tresorerie/{bank_a['id']}", json={"nom": "x"}
        ).status_code
        == 404
    )


def test_journal_can_be_filtered_by_treasury_account():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    treso = admin.get(f"/api/asso/{assoc}/tresorerie").json()
    banque = next(r for r in treso if r["numero"] == "512")
    caisse = next(r for r in treso if r["numero"] == "531")
    cats = admin.get(f"/api/asso/{assoc}/categories").json()
    cotis = next(c for c in cats if c["libelle"] == "Cotisations")

    for compte in (banque, caisse):
        admin.post(
            f"/api/asso/{assoc}/ecritures/simple",
            json={
                "categorie_id": cotis["id"],
                "compte_tresorerie_id": compte["id"],
                "montant": "10.00",
                "date": TODAY,
            },
        )

    only_bank = admin.get(
        f"/api/asso/{assoc}/ecritures", params={"compte_id": banque["id"]}
    ).json()
    assert len(only_bank) == 1
    assert len(admin.get(f"/api/asso/{assoc}/ecritures").json()) == 2


# --- Opening balance on an existing account (T1.1) -------------------------


def _bank(client: TestClient, assoc: str) -> dict:
    return next(
        r
        for r in client.get(f"/api/asso/{assoc}/tresorerie").json()
        if r["numero"] == "512"
    )


def test_set_opening_balance_on_a_seeded_account():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    bank = _bank(admin, assoc)
    assert _dec(bank["solde"]) == Decimal("0")

    resp = admin.post(
        f"/api/asso/{assoc}/tresorerie/{bank['id']}/solde-initial",
        json={"montant": "1000.00", "date_solde_initial": TODAY},
    )
    assert resp.status_code == 200, resp.text
    assert _dec(resp.json()["solde"]) == Decimal("1000.00")

    # One à-nouveau entry, counterpart on report à nouveau (110).
    entries = admin.get(f"/api/asso/{assoc}/ecritures").json()
    an = [e for e in entries if e["origine"] == "a_nouveau"]
    assert len(an) == 1
    balance = admin.get(f"/api/asso/{assoc}/balance").json()
    assert _dec(next(r for r in balance if r["numero"] == "110")["solde"]) == Decimal(
        "-1000.00"
    )


def test_opening_balance_is_validated_and_immutable():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    bank = _bank(admin, assoc)
    first = admin.post(
        f"/api/asso/{assoc}/tresorerie/{bank['id']}/solde-initial",
        json={"montant": "1000.00", "date_solde_initial": TODAY},
    )
    assert first.status_code == 200, first.text
    # Counts immediately (validated on creation): no validation step.
    assert _dec(first.json()["solde"]) == Decimal("1000.00")
    entries = admin.get(f"/api/asso/{assoc}/ecritures").json()
    an = next(e for e in entries if e["origine"] == "a_nouveau")
    assert an["statut"] == "validee"

    # A second attempt is refused: the opening balance is now immutable.
    resp = admin.post(
        f"/api/asso/{assoc}/tresorerie/{bank['id']}/solde-initial",
        json={"montant": "1500.00", "date_solde_initial": TODAY},
    )
    assert resp.status_code == 409


def test_zero_opening_balance_is_a_noop():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    bank = _bank(admin, assoc)
    resp = admin.post(
        f"/api/asso/{assoc}/tresorerie/{bank['id']}/solde-initial",
        json={"montant": "0", "date_solde_initial": TODAY},
    )
    assert resp.status_code == 200, resp.text
    assert _dec(resp.json()["solde"]) == Decimal("0")
    entries = admin.get(f"/api/asso/{assoc}/ecritures").json()
    assert [e for e in entries if e["origine"] == "a_nouveau"] == []


def test_cannot_change_a_validated_opening_balance():
    admin, assoc = _admin_with_association("admin@example.com", "alpha")
    bank = _bank(admin, assoc)
    admin.post(
        f"/api/asso/{assoc}/tresorerie/{bank['id']}/solde-initial",
        json={"montant": "1000.00", "date_solde_initial": TODAY},
    )
    an = next(
        e
        for e in admin.get(f"/api/asso/{assoc}/ecritures").json()
        if e["origine"] == "a_nouveau"
    )
    admin.post(f"/api/asso/{assoc}/ecritures/{an['id']}/validation")

    resp = admin.post(
        f"/api/asso/{assoc}/tresorerie/{bank['id']}/solde-initial",
        json={"montant": "2000.00", "date_solde_initial": TODAY},
    )
    assert resp.status_code == 409


def test_set_opening_balance_requires_permission(session: Session):
    _, assoc = _admin_with_association("admin@example.com", "alpha")
    viewer = _member_client(session, assoc, "view@example.com", Role.VIEWER)
    bank = _bank(viewer, assoc)
    resp = viewer.post(
        f"/api/asso/{assoc}/tresorerie/{bank['id']}/solde-initial",
        json={"montant": "100.00"},
    )
    assert resp.status_code == 403
