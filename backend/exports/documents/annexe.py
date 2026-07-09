"""Annexe ANC (PDF): narrative rubrics followed by the computed tables."""

from ..data import AnnexeData
from ..format import fmt_date
from ..pdf import INK, MUTED, AbacusPDF
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
        "Annexe aux comptes annuels de l'exercice : commentaires narratifs "
        "puis tableaux établis à partir des écritures validées (fonds dédiés, "
        "contributions volontaires en nature, immobilisations et amortissements, "
        "fonds propres).",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(3)

    _narrative_block(pdf, data)

    for section in data.sections:
        _compte_section(pdf, section.titre, section.lignes, section.total, "Total")
        pdf.ln(3)
    return pdf.to_bytes()


def _narrative_block(pdf: AbacusPDF, data: AnnexeData) -> None:
    """Render the filled-in narrative rubrics (skipped entirely when none)."""
    if not data.narrative:
        return
    for rubrique in data.narrative:
        pdf.set_font("plex", "B", 11)
        pdf.set_text_color(*INK)
        pdf.multi_cell(0, 6, rubrique.titre, new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("plex", "", 9)
        pdf.set_text_color(*MUTED)
        pdf.multi_cell(0, 5, rubrique.contenu, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)
