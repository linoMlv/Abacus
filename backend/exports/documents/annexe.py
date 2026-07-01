"""Annexe ANC (PDF)."""

from ..data import AnnexeData
from ..format import fmt_date
from ..pdf import MUTED, AbacusPDF
from .common import _compte_section


def annexe_pdf(association_name: str, data: AnnexeData) -> bytes:
    pdf = AbacusPDF(
        association_name=association_name,
        title="Annexe",
        subtitle=f"au {fmt_date(data.date_to)}",
    )
    pdf.add_page()
    pdf.set_font("plex", "", 9)
    pdf.set_text_color(*MUTED)
    pdf.multi_cell(
        0,
        5,
        "Tableaux établis à partir des écritures validées de l'exercice "
        "(fonds dédiés, contributions volontaires en nature, immobilisations et "
        "amortissements, fonds propres). Les commentaires narratifs sont à "
        "compléter séparément.",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(2)
    for section in data.sections:
        _compte_section(pdf, section.titre, section.lignes, section.total, "Total")
        pdf.ln(3)
    return pdf.to_bytes()
