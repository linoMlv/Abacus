"""Closing engine (pure): result determination and report à nouveau.

No I/O: the builders take the account soldes and return an unsaved, balanced
Ecriture (or None when there is nothing to book), validated against the balance
invariant.
"""

from datetime import date
from decimal import Decimal

import pytest

from accounting_engine import (
    EntryError,
    build_ecriture_determination_resultat,
    build_ecriture_report_a_nouveau,
    resultat_de_gestion,
    validate_lignes,
)
from models import EcritureOrigine

D = Decimal


def _determination(soldes):
    return build_ecriture_determination_resultat(
        association_id="assoc",
        exercice_id="ex",
        journal_id="od",
        soldes_gestion=soldes,
        compte_excedent_id="120",
        compte_deficit_id="129",
        date_ecriture=date(2026, 12, 31),
        numero_piece=10,
    )


def _lines(ecriture):
    return {(line.compte_id, line.debit, line.credit) for line in ecriture.lignes}


# --- Résultat de gestion --------------------------------------------------


def test_resultat_is_produits_minus_charges():
    # charge solde +100 (debit), produit solde -300 (credit) -> résultat +200.
    assert resultat_de_gestion([("6", D("100")), ("7", D("-300"))]) == D("200.00")
    assert resultat_de_gestion([("6", D("300")), ("7", D("-100"))]) == D("-200.00")
    assert resultat_de_gestion([]) == D("0.00")


# --- Détermination du résultat -------------------------------------------


def test_determination_books_an_excedent_to_120():
    ecriture = _determination([("charge", D("100.00")), ("produit", D("-300.00"))])
    assert ecriture is not None
    assert ecriture.origine is EcritureOrigine.CLOTURE
    validate_lignes(ecriture.lignes)
    assert _lines(ecriture) == {
        ("charge", D("0.00"), D("100.00")),  # charge crédité pour être soldé
        ("produit", D("300.00"), D("0.00")),  # produit débité pour être soldé
        ("120", D("0.00"), D("200.00")),  # excédent au crédit du résultat
    }


def test_determination_books_a_deficit_to_129():
    ecriture = _determination([("charge", D("300.00")), ("produit", D("-100.00"))])
    validate_lignes(ecriture.lignes)
    assert _lines(ecriture) == {
        ("charge", D("0.00"), D("300.00")),
        ("produit", D("100.00"), D("0.00")),
        ("129", D("200.00"), D("0.00")),  # déficit au débit du résultat
    }


def test_determination_ignores_zero_soldes():
    ecriture = _determination(
        [("a", D("0.00")), ("charge", D("50.00")), ("produit", D("-50.00"))]
    )
    # Balanced result (résultat 0): the two gestion lines suffice, no 12 line.
    assert _lines(ecriture) == {
        ("charge", D("0.00"), D("50.00")),
        ("produit", D("50.00"), D("0.00")),
    }


def test_determination_returns_none_without_gestion_movement():
    assert _determination([]) is None
    assert _determination([("a", D("0.00"))]) is None


# --- Report à nouveau ------------------------------------------------------


def _report(soldes_bilan, affectation):
    return build_ecriture_report_a_nouveau(
        association_id="assoc",
        exercice_id="ex2",
        journal_id="od",
        soldes_bilan=soldes_bilan,
        affectation_lignes=affectation,
        date_ecriture=date(2027, 1, 1),
        numero_piece=1,
    )


def test_report_carries_balances_and_affects_an_excedent():
    # Closing: cash 512 = +200 (actif), result +200 affected to report à nouveau.
    ecriture = _report([("512", D("200.00"))], [("110", D("0"), D("200.00"))])
    assert ecriture is not None
    assert ecriture.origine is EcritureOrigine.A_NOUVEAU
    validate_lignes(ecriture.lignes)
    assert _lines(ecriture) == {
        ("512", D("200.00"), D("0.00")),
        ("110", D("0.00"), D("200.00")),
    }


def test_report_affects_a_deficit_to_119():
    ecriture = _report([("512", D("-200.00"))], [("119", D("200.00"), D("0"))])
    validate_lignes(ecriture.lignes)
    assert _lines(ecriture) == {
        ("512", D("0.00"), D("200.00")),
        ("119", D("200.00"), D("0.00")),
    }


def test_report_can_split_between_report_and_reserves():
    ecriture = _report(
        [("512", D("200.00"))],
        [("110", D("0"), D("150.00")), ("106", D("0"), D("50.00"))],
    )
    validate_lignes(ecriture.lignes)
    assert _lines(ecriture) == {
        ("512", D("200.00"), D("0.00")),
        ("110", D("0.00"), D("150.00")),
        ("106", D("0.00"), D("50.00")),
    }


def test_report_returns_none_when_nothing_to_carry():
    assert _report([], []) is None


def test_report_rejects_an_unbalanced_affectation():
    # A wrong affectation total must never persist: the invariant catches it.
    with pytest.raises(EntryError):
        _report([("512", D("200.00"))], [("110", D("0"), D("100.00"))])
