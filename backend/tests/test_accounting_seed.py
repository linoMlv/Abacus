"""The default accounting referential and its seeding at association creation."""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from accounting_seed import DEFAULT_JOURNALS, PLAN_COMPTABLE_ANC
from database import get_session
from main import _fastapi_app as app
from models import Compte, Exercice, ExerciceStatut, Journal

PASSWORD = "password123"


@pytest.fixture(autouse=True)
def _use_test_session(session: Session):
    app.dependency_overrides[get_session] = lambda: session
    yield
    app.dependency_overrides.clear()


def _create_association(name: str, email: str, assoc_email: str) -> str:
    client = TestClient(app)
    reg = client.post(
        "/api/auth/register",
        json={"email": email, "password": PASSWORD, "name": "User"},
    )
    assert reg.status_code == 201, reg.text
    login = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200
    resp = client.post(
        "/api/auth/associations", json={"name": name, "email": assoc_email}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# --------------------------------------------------------------------------- #
# Chart integrity (pure)
# --------------------------------------------------------------------------- #
def test_account_numbers_are_unique():
    numeros = [n for n, _, _ in PLAN_COMPTABLE_ANC]
    assert len(numeros) == len(set(numeros))


def test_account_numbers_are_well_formed():
    for numero, _, _ in PLAN_COMPTABLE_ANC:
        assert numero.isdigit(), numero
        assert 1 <= int(numero[0]) <= 8, numero


def test_journal_codes_are_unique():
    codes = [c for c, _ in DEFAULT_JOURNALS]
    assert len(codes) == len(set(codes))


def test_key_associative_accounts_are_present():
    numeros = {n for n, _, _ in PLAN_COMPTABLE_ANC}
    # Cotisations, dons, subventions, banque/caisse, tiers, TVA, fonds dédiés,
    # report de ressources, contributions volontaires.
    for expected in (
        "756",
        "7541",
        "740",
        "512",
        "531",
        "401",
        "411",
        "44566",
        "44571",
        "1952",
        "689",
        "789",
        "875",
    ):
        assert expected in numeros, expected


# --------------------------------------------------------------------------- #
# Seeding at association creation
# --------------------------------------------------------------------------- #
def test_creating_an_association_seeds_the_referential(session: Session):
    assoc_id = _create_association("Asso", "u@example.com", "asso@example.com")

    journals = session.exec(
        select(Journal).where(Journal.association_id == assoc_id)
    ).all()
    assert {j.code for j in journals} == {c for c, _ in DEFAULT_JOURNALS}

    comptes = session.exec(
        select(Compte).where(Compte.association_id == assoc_id)
    ).all()
    assert len(comptes) == len(PLAN_COMPTABLE_ANC)
    assert all(c.is_active for c in comptes)

    exercices = session.exec(
        select(Exercice).where(Exercice.association_id == assoc_id)
    ).all()
    assert len(exercices) == 1
    exercice = exercices[0]
    year = date.today().year
    assert exercice.statut is ExerciceStatut.OUVERT
    assert exercice.libelle == str(year)
    assert exercice.date_debut == date(year, 1, 1)
    assert exercice.date_fin == date(year, 12, 31)


def test_each_association_gets_an_independent_chart(session: Session):
    assoc_a = _create_association("Asso A", "a@example.com", "aa@example.com")
    assoc_b = _create_association("Asso B", "b@example.com", "bb@example.com")

    count_a = len(
        session.exec(select(Compte).where(Compte.association_id == assoc_a)).all()
    )
    count_b = len(
        session.exec(select(Compte).where(Compte.association_id == assoc_b)).all()
    )
    assert count_a == count_b == len(PLAN_COMPTABLE_ANC)

    # No account is shared between associations.
    a_ids = {
        c.id
        for c in session.exec(
            select(Compte).where(Compte.association_id == assoc_a)
        ).all()
    }
    b_ids = {
        c.id
        for c in session.exec(
            select(Compte).where(Compte.association_id == assoc_b)
        ).all()
    }
    assert a_ids.isdisjoint(b_ids)
