"""Assisted posting engine: simple recette/dépense -> balanced double entry."""

from datetime import date
from decimal import Decimal

import pytest
from sqlmodel import Session, select

from accounting_engine import (
    EntryError,
    build_ecriture_extourne,
    build_ecriture_simple,
    next_numero_piece,
    validate_lignes,
)
from accounting_seed import seed_association_accounting
from models import (
    Association,
    CategorieSaisie,
    Compte,
    Ecriture,
    EcritureOrigine,
    EcritureStatut,
    Exercice,
    Journal,
    LigneEcriture,
    SensCategorie,
)


def _build(sens: SensCategorie, montant="150.00", numero=1) -> Ecriture:
    return build_ecriture_simple(
        association_id="assoc",
        exercice_id="ex",
        journal_id="jr",
        compte_tresorerie_id="512",
        compte_categorie_id="cat",
        sens=sens,
        montant=Decimal(montant),
        date_ecriture=date(2026, 6, 27),
        libelle="Test",
        numero_piece=numero,
    )


# --- Posting direction (pure) --------------------------------------------


def test_recette_debits_cash_and_credits_produit():
    ecriture = _build(SensCategorie.RECETTE)
    assert ecriture.statut == EcritureStatut.BROUILLON
    assert ecriture.origine == EcritureOrigine.SAISIE_SIMPLE
    debit, credit = ecriture.lignes
    assert debit.compte_id == "512" and debit.debit == Decimal("150.00")
    assert credit.compte_id == "cat" and credit.credit == Decimal("150.00")
    # The result is always balanced.
    validate_lignes(ecriture.lignes)


def test_depense_debits_charge_and_credits_cash():
    ecriture = _build(SensCategorie.DEPENSE)
    debit, credit = ecriture.lignes
    assert debit.compte_id == "cat" and debit.debit == Decimal("150.00")
    assert credit.compte_id == "512" and credit.credit == Decimal("150.00")
    validate_lignes(ecriture.lignes)


def test_zero_amount_is_rejected():
    with pytest.raises(EntryError, match="strictement positif"):
        _build(SensCategorie.RECETTE, montant="0")


def test_negative_amount_is_rejected():
    with pytest.raises(EntryError, match="négatif"):
        _build(SensCategorie.RECETTE, montant="-10.00")


# --- Sequential voucher numbering ----------------------------------------


def _seeded_association(session: Session) -> str:
    association = Association(name="A", email="a@example.com", password="x")
    session.add(association)
    session.flush()
    seed_association_accounting(session, association.id)
    session.commit()
    return association.id


def test_numero_piece_is_sequential_and_gapless(session: Session):
    assoc_id = _seeded_association(session)
    assert next_numero_piece(session, assoc_id) == 1

    exercice = session.exec(
        select(Exercice).where(Exercice.association_id == assoc_id)
    ).first()
    journal = session.exec(
        select(Journal).where(Journal.association_id == assoc_id, Journal.code == "VE")
    ).first()
    banque = session.exec(
        select(Compte).where(Compte.association_id == assoc_id, Compte.numero == "512")
    ).first()
    cotisations = session.exec(
        select(CategorieSaisie).where(
            CategorieSaisie.association_id == assoc_id,
            CategorieSaisie.libelle == "Cotisations",
        )
    ).first()

    ecriture = build_ecriture_simple(
        association_id=assoc_id,
        exercice_id=exercice.id,
        journal_id=journal.id,
        compte_tresorerie_id=banque.id,
        compte_categorie_id=cotisations.compte_id,
        sens=SensCategorie.RECETTE,
        montant=Decimal("150.00"),
        date_ecriture=date(2026, 6, 27),
        libelle="Cotisation Dupont",
        numero_piece=next_numero_piece(session, assoc_id),
    )
    session.add(ecriture)
    session.commit()

    # The next number follows on, with no gap.
    assert next_numero_piece(session, assoc_id) == 2


def test_numero_piece_is_isolated_per_association(session: Session):
    assoc_a = _seeded_association(session)
    association_b = Association(name="B", email="b@example.com", password="x")
    session.add(association_b)
    session.flush()
    seed_association_accounting(session, association_b.id)
    session.commit()

    # A's numbering does not leak into B: both start at 1 independently.
    exercice_a = session.exec(
        select(Exercice).where(Exercice.association_id == assoc_a)
    ).first()
    journal_a = session.exec(
        select(Journal).where(Journal.association_id == assoc_a)
    ).first()
    compte_a = session.exec(
        select(Compte).where(Compte.association_id == assoc_a, Compte.numero == "512")
    ).first()
    cat_a = session.exec(
        select(CategorieSaisie).where(CategorieSaisie.association_id == assoc_a)
    ).first()
    session.add(
        build_ecriture_simple(
            association_id=assoc_a,
            exercice_id=exercice_a.id,
            journal_id=journal_a.id,
            compte_tresorerie_id=compte_a.id,
            compte_categorie_id=cat_a.compte_id,
            sens=cat_a.sens,
            montant=Decimal("10.00"),
            date_ecriture=date(2026, 6, 27),
            libelle="x",
            numero_piece=next_numero_piece(session, assoc_a),
        )
    )
    session.commit()

    assert next_numero_piece(session, assoc_a) == 2
    assert next_numero_piece(session, association_b.id) == 1


def test_extourne_carries_the_analytic_tags():
    """A reversal must net the original in *every* dimension, so it carries the
    same catégorie / événement / tiers. Otherwise the Synthèse per-category and
    per-event breakdowns (which attribute by ``Ecriture.categorie_id`` /
    ``evenement_id``) stay inflated by every contre-passation, even though the
    result-by-class nets to zero."""
    original = Ecriture(
        association_id="assoc",
        exercice_id="ex",
        journal_id="jr",
        date=date(2026, 6, 27),
        numero_piece=1,
        libelle="Don",
        origine=EcritureOrigine.SAISIE_SIMPLE,
        categorie_id="cat-1",
        evenement_id="ev-1",
        tiers_id="tiers-1",
        reference_externe="FAC-42",
        lignes=[
            LigneEcriture(
                compte_id="512",
                libelle="",
                debit=Decimal("100.00"),
                credit=Decimal("0.00"),
            ),
            LigneEcriture(
                compte_id="756",
                libelle="",
                debit=Decimal("0.00"),
                credit=Decimal("100.00"),
            ),
        ],
    )

    reversal = build_ecriture_extourne(original=original, numero_piece=2)

    assert reversal.origine is EcritureOrigine.EXTOURNE
    # The analytic tags are carried over so every breakdown nets out.
    assert reversal.categorie_id == "cat-1"
    assert reversal.evenement_id == "ev-1"
    assert reversal.tiers_id == "tiers-1"
    # Debit/credit are swapped line by line.
    assert [(line.debit, line.credit) for line in reversal.lignes] == [
        (Decimal("0.00"), Decimal("100.00")),
        (Decimal("100.00"), Decimal("0.00")),
    ]
