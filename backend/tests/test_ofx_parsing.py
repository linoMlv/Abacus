"""The OFX statement parser: signed amounts, labels, FITID, both flavours."""

from datetime import date
from decimal import Decimal

import pytest

from banque import ReleveParseError, parse_releve_ofx

# OFX 1.x (SGML) — the flavour most French banks export. OFX is insensitive to
# whitespace between tags, so one tag per line keeps the sample readable.
OFX_SGML = b"""OFXHEADER:100
DATA:OFXSGML
VERSION:102

<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><CURDEF>EUR
<BANKACCTFROM><BANKID>30001<ACCTID>000123<ACCTTYPE>CHECKING</BANKACCTFROM>
<BANKTRANLIST>
<STMTTRN>
<TRNTYPE>CREDIT
<DTPOSTED>20260615
<TRNAMT>150.00
<FITID>ABC1
<NAME>Cotisation Dupont
<MEMO>vir
</STMTTRN>
<STMTTRN>
<TRNTYPE>DEBIT
<DTPOSTED>20260618
<TRNAMT>-8.00
<FITID>ABC2
<NAME>Frais
</STMTTRN>
</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>"""

# OFX 2.x (XML).
OFX_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<?OFX OFXHEADER="200" VERSION="211" SECURITY="NONE"?>
<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><CURDEF>EUR</CURDEF>
<BANKACCTFROM><BANKID>30001</BANKID><ACCTID>000123</ACCTID>
<ACCTTYPE>CHECKING</ACCTTYPE></BANKACCTFROM>
<BANKTRANLIST>
<STMTTRN>
<TRNTYPE>CREDIT</TRNTYPE>
<DTPOSTED>20260615</DTPOSTED>
<TRNAMT>150.00</TRNAMT>
<FITID>ABC1</FITID>
<NAME>Cotisation Dupont</NAME>
</STMTTRN>
</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>"""


def test_parses_ofx_sgml_with_signed_amounts_and_fitid():
    lignes = parse_releve_ofx(OFX_SGML)
    assert len(lignes) == 2

    credit = lignes[0]
    assert credit.date_operation == date(2026, 6, 15)
    assert credit.montant == Decimal("150.00")
    assert credit.fitid == "ABC1"
    assert "Cotisation Dupont" in credit.libelle

    # An outflow keeps its negative sign.
    assert lignes[1].montant == Decimal("-8.00")
    assert lignes[1].fitid == "ABC2"


def test_parses_ofx_xml():
    (ligne,) = parse_releve_ofx(OFX_XML)
    assert ligne.date_operation == date(2026, 6, 15)
    assert ligne.montant == Decimal("150.00")
    assert ligne.fitid == "ABC1"


def test_unreadable_ofx_raises():
    with pytest.raises(ReleveParseError):
        parse_releve_ofx(b"this is not an ofx file at all")
