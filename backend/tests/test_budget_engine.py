"""Budget engine (pure computation): réalisé per category over an exercice and
the prévu/réalisé/écart assembly.

Réalisé counts the validated class-6/7 movement of the entries tagged with each
category, signed by the category's sens (a recette is credited, a dépense
debited). Drafts and other exercices never leak into the figure. The assembly
layer combines a prévu map with the réalisé map into a view with totals and a
prévisionnel result.
"""

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from budget_engine import (
    BudgetLigneView,
    build_budget_view,
    overruns,
    realise_par_categorie,
)
from database import get_session
from main import _fastapi_app as app
from models import CategorieSaisie, Exercice, SensCategorie

PASSWORD = "password123"
TODAY = "2026-06-27"


@pytest.fixture(autouse=True)
def _use_test_session(session: Session):
    app.dependency_overrides[get_session] = lambda: session
    yield
    app.dependency_overrides.clear()


def _admin_with_association(email: str, name: str) -> tuple[TestClient, str]:
    client = TestClient(app)
    client.post(
        "/api/auth/register",
        json={"email": email, "password": PASSWORD, "name": "User"},
    )
    client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    resp = client.post(
        "/api/auth/associations", json={"name": name, "email": f"{name}@example.com"}
    )
    assert resp.status_code == 201, resp.text
    return client, resp.json()["id"]


def _categorie_id(client: TestClient, assoc: str, libelle: str) -> str:
    cats = client.get(f"/api/asso/{assoc}/categories").json()
    return next(c["id"] for c in cats if c["libelle"] == libelle)


def _treso_id(client: TestClient, assoc: str, numero: str) -> str:
    comptes = client.get(f"/api/asso/{assoc}/tresorerie").json()
    return next(c["id"] for c in comptes if c["numero"] == numero)


def _post_simple(
    client: TestClient, assoc: str, libelle: str, montant: str, validate: bool = True
) -> dict:
    resp = client.post(
        f"/api/asso/{assoc}/ecritures/simple",
        json={
            "categorie_id": _categorie_id(client, assoc, libelle),
            "compte_tresorerie_id": _treso_id(client, assoc, "512"),
            "montant": montant,
            "date": TODAY,
        },
    )
    assert resp.status_code == 201, resp.text
    entry = resp.json()
    if validate:
        client.post(f"/api/asso/{assoc}/ecritures/{entry['id']}/validation")
    return entry


def _open_exercice(session: Session, assoc: str) -> Exercice:
    return session.exec(
        select(Exercice).where(Exercice.association_id == assoc)
    ).first()


def _categories(session: Session, assoc: str) -> list[CategorieSaisie]:
    return session.exec(
        select(CategorieSaisie).where(CategorieSaisie.association_id == assoc)
    ).all()


# --- réalisé ---------------------------------------------------------------


def test_realise_sums_validated_movement_signed_by_sens(session: Session):
    admin, assoc = _admin_with_association("a@example.com", "alpha")
    _post_simple(admin, assoc, "Cotisations", "150.00")  # recette (produit 756)
    _post_simple(admin, assoc, "Locations", "100.00")  # dépense (charge 613)
    exercice = _open_exercice(session, assoc)

    realise = realise_par_categorie(session, assoc, exercice.id)

    cot = _categorie_id(admin, assoc, "Cotisations")
    loc = _categorie_id(admin, assoc, "Locations")
    assert realise[cot] == Decimal("150.00")  # credit − debit on class 7
    assert realise[loc] == Decimal("100.00")  # debit − credit on class 6


def test_realise_excludes_drafts(session: Session):
    admin, assoc = _admin_with_association("a@example.com", "alpha")
    _post_simple(admin, assoc, "Cotisations", "150.00", validate=True)
    _post_simple(admin, assoc, "Cotisations", "999.00", validate=False)  # draft
    exercice = _open_exercice(session, assoc)

    realise = realise_par_categorie(session, assoc, exercice.id)

    cot = _categorie_id(admin, assoc, "Cotisations")
    assert realise[cot] == Decimal("150.00")  # the draft is not counted


def test_realise_is_scoped_to_the_exercice(session: Session):
    admin, assoc = _admin_with_association("a@example.com", "alpha")
    _post_simple(admin, assoc, "Cotisations", "150.00")
    # A brand-new empty exercice sees nothing of the seeded year's movements.
    empty = Exercice(
        association_id=assoc,
        libelle="2099",
        date_debut=date(2099, 1, 1),
        date_fin=date(2099, 12, 31),
    )
    session.add(empty)
    session.commit()

    assert realise_par_categorie(session, assoc, empty.id) == {}


# --- assembly --------------------------------------------------------------


def test_build_view_totals_and_ecart(session: Session):
    admin, assoc = _admin_with_association("a@example.com", "alpha")
    cats = _categories(session, assoc)
    cot = next(c for c in cats if c.libelle == "Cotisations")
    loc = next(c for c in cats if c.libelle == "Locations")

    view = build_budget_view(
        cats,
        prevu={cot.id: Decimal("8000.00"), loc.id: Decimal("1200.00")},
        realise={cot.id: Decimal("6200.00"), loc.id: Decimal("1500.00")},
    )

    by_id = {ligne.categorie_id: ligne for ligne in view.lignes}
    assert by_id[cot.id].montant_prevu == Decimal("8000.00")
    assert by_id[cot.id].realise == Decimal("6200.00")
    assert by_id[cot.id].ecart == Decimal("-1800.00")
    assert by_id[loc.id].ecart == Decimal("300.00")  # over budget (dépense)
    # Every active category is present, even those without a budget line.
    assert len(view.lignes) == len(cats)

    assert view.total_recettes_prevu == Decimal("8000.00")
    assert view.total_recettes_realise == Decimal("6200.00")
    assert view.total_depenses_prevu == Decimal("1200.00")
    assert view.total_depenses_realise == Decimal("1500.00")
    assert view.resultat_prevu == Decimal("6800.00")
    assert view.resultat_realise == Decimal("4700.00")


def test_build_view_orders_recettes_before_depenses(session: Session):
    admin, assoc = _admin_with_association("a@example.com", "alpha")
    cats = _categories(session, assoc)

    view = build_budget_view(cats, prevu={}, realise={})

    senses = [ligne.sens for ligne in view.lignes]
    first_depense = senses.index(SensCategorie.DEPENSE)
    assert all(s == SensCategorie.RECETTE for s in senses[:first_depense])
    assert all(s == SensCategorie.DEPENSE for s in senses[first_depense:])


def test_overruns_only_depenses_over_a_positive_budget(session: Session):
    admin, assoc = _admin_with_association("a@example.com", "alpha")
    cats = _categories(session, assoc)
    loc = next(c for c in cats if c.libelle == "Locations")
    hono = next(c for c in cats if c.libelle == "Honoraires")
    cot = next(c for c in cats if c.libelle == "Cotisations")

    view = build_budget_view(
        cats,
        prevu={
            loc.id: Decimal("1000.00"),  # over
            hono.id: Decimal("500.00"),  # under
            cot.id: Decimal("100.00"),  # recette over target — not an overrun
        },
        realise={
            loc.id: Decimal("1500.00"),
            hono.id: Decimal("300.00"),
            cot.id: Decimal("9999.00"),
        },
    )

    over = overruns(view)
    assert isinstance(over[0], BudgetLigneView)
    assert [ligne.categorie_id for ligne in over] == [loc.id]
