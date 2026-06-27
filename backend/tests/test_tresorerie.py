"""Treasury accounts: seeding, model metadata, CRUD endpoints, balances.

A treasury account is a class-5 ``Compte`` carrying a ``type_tresorerie`` (§15.4):
ordinary chart-of-accounts lines leave it null. The seed marks the generic
512/531 as the association's starting bank/cash accounts so the app works out of
the box; users rename them, set opening balances and add more.
"""

from datetime import date

from sqlmodel import Session, select

from accounting_seed import seed_association_accounting
from models import Association, Compte, TypeTresorerie


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
