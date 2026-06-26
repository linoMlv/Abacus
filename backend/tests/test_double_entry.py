"""Double-entry core: balance invariant + persistence/uniqueness guarantees."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from accounting_engine import EntryError, validate_lignes
from accounting_seed import seed_association_accounting
from models import (
    Association,
    Compte,
    Ecriture,
    EcritureOrigine,
    EcritureStatut,
    Exercice,
    Journal,
    LigneEcriture,
)


def _ligne(debit="0", credit="0", compte_id="c") -> LigneEcriture:
    return LigneEcriture(
        compte_id=compte_id,
        libelle="x",
        debit=Decimal(debit),
        credit=Decimal(credit),
    )


# --- Balance invariant (pure) --------------------------------------------


def test_balanced_two_line_entry_is_valid():
    validate_lignes([_ligne(debit="150.00"), _ligne(credit="150.00")])


def test_balanced_multi_line_entry_is_valid():
    # Achat 100 TTC avec TVA 20 % : D 83.33 charge + D 16.67 TVA / C 100 banque.
    validate_lignes(
        [
            _ligne(debit="83.33"),
            _ligne(debit="16.67"),
            _ligne(credit="100.00"),
        ]
    )


def test_unbalanced_entry_is_rejected():
    with pytest.raises(EntryError, match="déséquilibrée"):
        validate_lignes([_ligne(debit="150.00"), _ligne(credit="149.99")])


def test_entry_needs_at_least_two_lines():
    with pytest.raises(EntryError, match="au moins deux lignes"):
        validate_lignes([_ligne(debit="150.00")])


def test_line_cannot_carry_both_debit_and_credit():
    with pytest.raises(EntryError, match="débit et un crédit"):
        validate_lignes([_ligne(debit="10.00", credit="10.00"), _ligne(credit="0")])


def test_line_must_carry_an_amount():
    with pytest.raises(EntryError, match="débit ou au crédit"):
        validate_lignes([_ligne(), _ligne(credit="0")])


def test_negative_amount_is_rejected():
    with pytest.raises(EntryError, match="négatif"):
        validate_lignes([_ligne(debit="-150.00"), _ligne(credit="-150.00")])


def test_zero_total_entry_is_rejected():
    # Two lines that individually carry a side but net to zero on each total.
    with pytest.raises(EntryError):
        validate_lignes([_ligne(debit="0"), _ligne(credit="0")])


# --- Persistence & uniqueness --------------------------------------------


def _seeded_association(session: Session) -> str:
    association = Association(name="A", email="a@example.com", password="x")
    session.add(association)
    session.flush()
    seed_association_accounting(session, association.id)
    session.commit()
    return association.id


def test_entry_round_trips_with_balanced_lines(session: Session):
    assoc_id = _seeded_association(session)
    exercice = session.exec(
        select(Exercice).where(Exercice.association_id == assoc_id)
    ).first()
    journal = session.exec(
        select(Journal).where(Journal.association_id == assoc_id, Journal.code == "BQ")
    ).first()
    banque = session.exec(
        select(Compte).where(Compte.association_id == assoc_id, Compte.numero == "512")
    ).first()
    cotis = session.exec(
        select(Compte).where(Compte.association_id == assoc_id, Compte.numero == "756")
    ).first()

    ecriture = Ecriture(
        association_id=assoc_id,
        exercice_id=exercice.id,
        journal_id=journal.id,
        date=date(2026, 6, 27),
        numero_piece=1,
        libelle="Cotisation",
        origine=EcritureOrigine.SAISIE_SIMPLE,
        lignes=[
            LigneEcriture(
                compte_id=banque.id, libelle="Banque", debit=Decimal("150.00")
            ),
            LigneEcriture(
                compte_id=cotis.id, libelle="Cotisation", credit=Decimal("150.00")
            ),
        ],
    )
    session.add(ecriture)
    session.commit()

    reloaded = session.get(Ecriture, ecriture.id)
    assert reloaded.statut == EcritureStatut.BROUILLON
    assert len(reloaded.lignes) == 2
    assert sum(line.debit for line in reloaded.lignes) == Decimal("150.00")
    assert sum(line.credit for line in reloaded.lignes) == Decimal("150.00")

    # Deleting the voucher cascades to its lines.
    session.delete(reloaded)
    session.commit()
    assert session.exec(select(LigneEcriture)).all() == []


def test_voucher_number_is_unique_per_association(session: Session):
    assoc_id = _seeded_association(session)
    exercice = session.exec(
        select(Exercice).where(Exercice.association_id == assoc_id)
    ).first()
    journal = session.exec(
        select(Journal).where(Journal.association_id == assoc_id)
    ).first()

    def _make() -> Ecriture:
        return Ecriture(
            association_id=assoc_id,
            exercice_id=exercice.id,
            journal_id=journal.id,
            date=date(2026, 6, 27),
            numero_piece=1,
            libelle="x",
            origine=EcritureOrigine.MANUELLE,
        )

    session.add(_make())
    session.commit()

    session.add(_make())
    with pytest.raises(IntegrityError):
        session.commit()
