"""The bank-statement CSV parser: signed amounts, formats, hostile input."""

from datetime import date
from decimal import Decimal

import pytest

from banque import ColumnMapping, ReleveParseError, parse_releve_csv


def test_parses_a_signed_montant_column():
    content = (
        "Date;Libelle;Montant\n"
        "15/06/2026;Cotisation Dupont;150,00\n"
        "18/06/2026;Achat fournitures;-89,90\n"
    )
    mapping = ColumnMapping(date=0, libelle=1, montant=2)
    lignes = parse_releve_csv(content, mapping)

    assert len(lignes) == 2
    assert lignes[0].date_operation == date(2026, 6, 15)
    assert lignes[0].libelle == "Cotisation Dupont"
    assert lignes[0].montant == Decimal("150.00")
    # An outflow keeps its negative sign.
    assert lignes[1].montant == Decimal("-89.90")


def test_parses_separate_debit_credit_columns():
    content = (
        "Date,Libelle,Debit,Credit\n"
        "2026-06-15,Cotisation,,150.00\n"
        "2026-06-18,Fournitures,89.90,\n"
    )
    mapping = ColumnMapping(
        date=0,
        libelle=1,
        debit=2,
        credit=3,
        date_format="%Y-%m-%d",
        decimal_sep=".",
        delimiter=",",
    )
    lignes = parse_releve_csv(content, mapping)

    # Credit is an inflow (+), debit an outflow (−); net signed montant.
    assert lignes[0].montant == Decimal("150.00")
    assert lignes[1].montant == Decimal("-89.90")


def test_thousands_separator_and_nbsp_are_stripped():
    content = "Date;Libelle;Montant\n01/01/2026;Grosse recette;1 234,56\n"
    mapping = ColumnMapping(date=0, libelle=1, montant=2)
    (ligne,) = parse_releve_csv(content, mapping)
    assert ligne.montant == Decimal("1234.56")


def test_blank_lines_are_skipped():
    content = "Date;Libelle;Montant\n\n15/06/2026;X;10,00\n   \n"
    mapping = ColumnMapping(date=0, libelle=1, montant=2)
    lignes = parse_releve_csv(content, mapping)
    assert len(lignes) == 1


def test_no_amount_column_is_rejected():
    mapping = ColumnMapping(date=0, libelle=1)
    with pytest.raises(ReleveParseError):
        parse_releve_csv("Date;Libelle\n01/01/2026;X\n", mapping)


def test_bad_date_raises_with_row_number():
    content = "Date;Libelle;Montant\nnot-a-date;X;10,00\n"
    mapping = ColumnMapping(date=0, libelle=1, montant=2)
    with pytest.raises(ReleveParseError):
        parse_releve_csv(content, mapping)


def test_bad_amount_raises():
    content = "Date;Libelle;Montant\n01/01/2026;X;abc\n"
    mapping = ColumnMapping(date=0, libelle=1, montant=2)
    with pytest.raises(ReleveParseError):
        parse_releve_csv(content, mapping)


def test_missing_column_index_raises():
    content = "Date;Libelle;Montant\n01/01/2026;X\n"  # row is short
    mapping = ColumnMapping(date=0, libelle=1, montant=2)
    with pytest.raises(ReleveParseError):
        parse_releve_csv(content, mapping)
