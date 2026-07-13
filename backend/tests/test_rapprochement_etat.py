"""Per-treasury-account reconciliation state (page Comptes, C25).

Read-only summary: what the books say, what the last statement said, and the gap
the not-yet-reconciled lines explain. No statement content leaks here — counts and
totals only — so it sits behind REPORT_VIEW like any other restitution.
"""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from database import get_session
from main import _fastapi_app as app
from models import Membership, Role

PASSWORD = "password123"

CSV_TWO = (
    "Date;Libelle;Montant\n"
    "15/06/2026;Cotisation Dupont;150,00\n"
    "18/06/2026;Frais tenue de compte;-8,00\n"
)


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


def _treasury_id(client: TestClient, assoc: str, numero: str) -> str:
    rows = client.get(f"/api/asso/{assoc}/tresorerie").json()
    return next(r["id"] for r in rows if r["numero"] == numero)


def _import(client: TestClient, assoc: str, compte_id: str, content: str):
    resp = client.post(
        f"/api/asso/{assoc}/banque/import",
        data={
            "compte_id": compte_id,
            "date_col": "0",
            "libelle_col": "1",
            "montant_col": "2",
        },
        files={"fichier": ("releve.csv", content.encode("utf-8"), "text/csv")},
    )
    assert resp.status_code == 201, resp.text


def _etat(client: TestClient, assoc: str) -> dict[str, dict]:
    resp = client.get(f"/api/asso/{assoc}/banque/rapprochement")
    assert resp.status_code == 200, resp.text
    return {row["compte_id"]: row for row in resp.json()}


def _dec(value) -> Decimal:
    return Decimal(str(value))


def test_state_covers_every_treasury_account_even_without_any_import():
    admin, assoc = _admin_with_association("a@example.com", "alpha")
    bank = _treasury_id(admin, assoc, "512")
    caisse = _treasury_id(admin, assoc, "531")

    etat = _etat(admin, assoc)

    assert set(etat) == {bank, caisse}
    ligne = etat[bank]
    assert ligne["nb_non_rapprochees"] == 0
    assert _dec(ligne["montant_non_rapproche"]) == Decimal("0")
    assert _dec(ligne["solde_comptable"]) == Decimal("0")
    assert ligne["dernier_import"] is None


def test_unreconciled_lines_explain_the_gap_with_the_books():
    """The estimated bank balance = books + what the bank saw but we did not book."""
    admin, assoc = _admin_with_association("b@example.com", "beta")
    bank = _treasury_id(admin, assoc, "512")
    _import(admin, assoc, bank, CSV_TWO)

    ligne = _etat(admin, assoc)[bank]

    assert ligne["nb_non_rapprochees"] == 2
    assert _dec(ligne["montant_non_rapproche"]) == Decimal("142.00")  # 150 - 8
    assert _dec(ligne["solde_comptable"]) == Decimal("0")
    assert _dec(ligne["solde_bancaire_estime"]) == Decimal("142.00")
    assert ligne["dernier_import"] is not None


def test_reconciled_lines_leave_the_state_clean():
    admin, assoc = _admin_with_association("c@example.com", "gamma")
    bank = _treasury_id(admin, assoc, "512")
    _import(admin, assoc, bank, CSV_TWO)
    lignes = admin.get(f"/api/asso/{assoc}/banque/lignes").json()

    for ligne in lignes:
        admin.post(f"/api/asso/{assoc}/banque/lignes/{ligne['id']}/ignorer?ignore=true")

    etat = _etat(admin, assoc)[bank]
    assert etat["nb_non_rapprochees"] == 0
    assert _dec(etat["montant_non_rapproche"]) == Decimal("0")


def test_a_viewer_may_read_the_state(session: Session):
    admin, assoc = _admin_with_association("e@example.com", "epsilon")
    bank = _treasury_id(admin, assoc, "512")
    _import(admin, assoc, bank, CSV_TWO)
    viewer = _member_client(session, assoc, "viewer@example.com", Role.VIEWER)

    assert viewer.get(f"/api/asso/{assoc}/banque/rapprochement").status_code == 200
    assert _etat(viewer, assoc)[bank]["nb_non_rapprochees"] == 2


def test_the_state_of_another_association_is_not_reachable():
    _, assoc_a = _admin_with_association("f@example.com", "zeta")
    client_b, _ = _admin_with_association("g@example.com", "eta")

    assert client_b.get(f"/api/asso/{assoc_a}/banque/rapprochement").status_code == 404
