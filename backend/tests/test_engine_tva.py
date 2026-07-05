"""VAT-aware assisted posting engine (pure): TTC → HT + TVA split.

No I/O: the caller resolves the déductible/collectée account and passes it in;
the builder returns an unsaved, balanced Ecriture. TVA is optional — without a
rate the entry stays a plain two-line simple entry (backward compatible).
"""

from datetime import date
from decimal import Decimal

import pytest

from accounting_engine import (
    EntryError,
    build_ecriture_simple,
    split_ttc,
    validate_lignes,
)
from models import SensCategorie

D = Decimal


def _build(sens, *, montant="100.00", tva_taux=None, compte_tva_id="44566"):
    return build_ecriture_simple(
        association_id="assoc",
        exercice_id="ex",
        journal_id="jr",
        compte_tresorerie_id="512",
        compte_categorie_id="cat",
        sens=sens,
        montant=D(montant),
        date_ecriture=date(2026, 6, 27),
        libelle="Test",
        numero_piece=1,
        tva_taux=tva_taux,
        compte_tva_id=compte_tva_id,
    )


# --- Pure TTC split -------------------------------------------------------


def test_split_20_percent():
    ht, tva = split_ttc(D("100.00"), D("20"))
    assert ht == D("83.33")
    assert tva == D("16.67")
    # The split always reconstitutes the TTC exactly (no rounding drift).
    assert ht + tva == D("100.00")


def test_split_reduced_rate_reconstitutes_ttc():
    ht, tva = split_ttc(D("10.00"), D("5.5"))
    assert ht + tva == D("10.00")
    assert tva == D("0.52")


def test_split_zero_rate_is_all_ht():
    assert split_ttc(D("100.00"), D("0")) == (D("100.00"), D("0.00"))


def test_split_rejects_out_of_range_rate():
    with pytest.raises(EntryError):
        split_ttc(D("100.00"), D("120"))
    with pytest.raises(EntryError):
        split_ttc(D("100.00"), D("-1"))


# --- VAT lines on the entry ----------------------------------------------


def test_depense_with_tva_books_deductible_debit():
    """Dépense 100 TTC @ 20 % → D charge 83,33 + D 44566 16,67 / C 512 100."""
    ecriture = _build(SensCategorie.DEPENSE, tva_taux=D("20"), compte_tva_id="44566")
    lignes = {(li.compte_id, li.debit, li.credit) for li in ecriture.lignes}
    assert lignes == {
        ("cat", D("83.33"), D("0.00")),
        ("44566", D("16.67"), D("0.00")),
        ("512", D("0.00"), D("100.00")),
    }
    validate_lignes(ecriture.lignes)
    # The base (HT) line records the rate and amount for traceability / display.
    base = next(li for li in ecriture.lignes if li.compte_id == "cat")
    assert base.tva_taux == D("20")
    assert base.tva_montant == D("16.67")


def test_recette_with_tva_books_collectee_credit():
    """Recette 100 TTC @ 20 % → D 512 100 / C produit 83,33 + C 44571 16,67."""
    ecriture = _build(SensCategorie.RECETTE, tva_taux=D("20"), compte_tva_id="44571")
    lignes = {(li.compte_id, li.debit, li.credit) for li in ecriture.lignes}
    assert lignes == {
        ("512", D("100.00"), D("0.00")),
        ("cat", D("0.00"), D("83.33")),
        ("44571", D("0.00"), D("16.67")),
    }
    validate_lignes(ecriture.lignes)


def test_no_rate_stays_two_lines():
    ecriture = _build(SensCategorie.DEPENSE, tva_taux=None)
    assert len(ecriture.lignes) == 2
    base = next(li for li in ecriture.lignes if li.compte_id == "cat")
    assert base.tva_taux is None and base.tva_montant is None


def test_zero_rate_stays_two_lines():
    ecriture = _build(SensCategorie.DEPENSE, tva_taux=D("0"))
    assert len(ecriture.lignes) == 2


def test_rate_without_tva_account_is_rejected():
    with pytest.raises(EntryError):
        _build(SensCategorie.DEPENSE, tva_taux=D("20"), compte_tva_id=None)
