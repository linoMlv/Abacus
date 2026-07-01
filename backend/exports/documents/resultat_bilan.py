"""Compte de résultat & bilan ANC (PDF)."""

from ..data import BilanData, CompteResultatData
from ..format import fmt_amount, fmt_date
from ..pdf import MUTED, AbacusPDF
from .common import (
    _COMPTE_ALIGNS,
    _COMPTE_HEADERS,
    _COMPTE_WIDTHS,
    _compte_section,
    _period_subtitle,
    _resultat_banner,
)


def compte_resultat_pdf(association_name: str, data: CompteResultatData) -> bytes:
    pdf = AbacusPDF(
        association_name=association_name,
        title="Compte de résultat",
        subtitle=_period_subtitle(data.date_from, data.date_to),
    )
    pdf.add_page()
    _compte_section(
        pdf, "Charges", data.charges, data.total_charges, "Total des charges"
    )
    pdf.ln(3)
    _compte_section(
        pdf, "Produits", data.produits, data.total_produits, "Total des produits"
    )
    _resultat_banner(pdf, data.resultat)
    return pdf.to_bytes()


def bilan_pdf(association_name: str, data: BilanData) -> bytes:
    pdf = AbacusPDF(
        association_name=association_name,
        title="Bilan",
        subtitle=f"au {fmt_date(data.date_to)}",
    )
    pdf.add_page()
    _compte_section(pdf, "Actif", data.actif, data.total_actif, "Total de l'actif")
    pdf.ln(3)

    pdf.section_title("Passif")
    rows = [
        [ligne.numero, ligne.libelle, fmt_amount(ligne.montant)]
        for ligne in data.passif
    ]
    rows.append(["", "Résultat de l'exercice", fmt_amount(data.resultat)])
    pdf.table(
        _COMPTE_HEADERS,
        rows,
        widths=_COMPTE_WIDTHS,
        aligns=_COMPTE_ALIGNS,
        total_row=["", "Total du passif", fmt_amount(data.total_passif)],
    )

    pdf.ln(2)
    pdf.set_font("plex", "", 9)
    pdf.set_text_color(*MUTED)
    balanced = data.total_actif == data.total_passif
    note = (
        "Bilan équilibré (actif = passif)."
        if balanced
        else "Attention : l'actif et le passif ne s'équilibrent pas."
    )
    pdf.cell(0, 6, note, new_x="LMARGIN", new_y="NEXT")
    return pdf.to_bytes()
