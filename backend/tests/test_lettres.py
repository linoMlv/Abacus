"""French amount-in-words (pure), for the fiscal receipt."""

from decimal import Decimal

from exports.lettres import montant_en_lettres, nombre_en_lettres

D = Decimal


def test_units_and_teens():
    assert nombre_en_lettres(0) == "zéro"
    assert nombre_en_lettres(7) == "sept"
    assert nombre_en_lettres(16) == "seize"
    assert nombre_en_lettres(17) == "dix-sept"


def test_tens_with_et_and_hyphen():
    assert nombre_en_lettres(21) == "vingt et un"
    assert nombre_en_lettres(22) == "vingt-deux"
    assert nombre_en_lettres(71) == "soixante et onze"
    assert nombre_en_lettres(72) == "soixante-douze"


def test_quatre_vingts_rules():
    assert nombre_en_lettres(80) == "quatre-vingts"
    assert nombre_en_lettres(81) == "quatre-vingt-un"  # no "et", no final "s"
    assert nombre_en_lettres(90) == "quatre-vingt-dix"
    assert nombre_en_lettres(91) == "quatre-vingt-onze"


def test_hundreds_plural_rules():
    assert nombre_en_lettres(100) == "cent"
    assert nombre_en_lettres(101) == "cent un"
    assert nombre_en_lettres(200) == "deux cents"  # plural: multiplied, nothing after
    assert nombre_en_lettres(201) == "deux cent un"  # singular: followed by a number
    assert nombre_en_lettres(500) == "cinq cents"


def test_thousands_and_millions():
    assert nombre_en_lettres(1000) == "mille"
    assert nombre_en_lettres(1980) == "mille neuf cent quatre-vingts"
    assert nombre_en_lettres(2000) == "deux mille"  # "mille" is invariable
    assert nombre_en_lettres(1_000_000) == "un million"
    assert nombre_en_lettres(2_000_000) == "deux millions"


def test_montant_euros():
    assert montant_en_lettres(D("500.00")) == "cinq cents euros"
    assert montant_en_lettres(D("1.00")) == "un euro"
    assert montant_en_lettres(D("0.00")) == "zéro euro"


def test_montant_with_centimes():
    assert montant_en_lettres(D("12.50")) == "douze euros et cinquante centimes"
    assert montant_en_lettres(D("1.01")) == "un euro et un centime"
