"""Shared PDF helpers and account-table layout for the document builders."""

from ..data import LigneCompte
from ..format import fmt_amount, fmt_date, fmt_eur
from ..pdf import DEPENSE, MUTED, RECETTE, AbacusPDF

_COMPTE_HEADERS = ["Compte", "Libellé", "Montant"]
_COMPTE_WIDTHS = (22, 64, 28)
_COMPTE_ALIGNS = ("LEFT", "LEFT", "RIGHT")


def _amount_or_blank(value) -> str:
    return fmt_amount(value) if value else ""


def _opt_eur(value) -> str:
    return fmt_eur(value) if value is not None else "—"


def _period_subtitle(date_from, date_to) -> str:
    return f"Période du {fmt_date(date_from)} au {fmt_date(date_to)}"


def _empty_note(pdf: AbacusPDF, text: str) -> None:
    pdf.set_font("plex", "", 10)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 8, text, new_x="LMARGIN", new_y="NEXT")


def _compte_section(
    pdf: AbacusPDF,
    title: str,
    lignes: list[LigneCompte],
    total: object,
    total_label: str,
) -> None:
    pdf.section_title(title)
    if not lignes:
        _empty_note(pdf, "Aucun mouvement.")
        pdf.ln(2)
        return
    rows = [
        [ligne.numero, ligne.libelle, fmt_amount(ligne.montant)] for ligne in lignes
    ]
    pdf.table(
        _COMPTE_HEADERS,
        rows,
        widths=_COMPTE_WIDTHS,
        aligns=_COMPTE_ALIGNS,
        total_row=["", total_label, fmt_amount(total)],
    )


def _resultat_banner(pdf: AbacusPDF, resultat) -> None:
    color = RECETTE if resultat >= 0 else DEPENSE
    pdf.ln(2)
    pdf.set_font("plex", "B", 13)
    pdf.set_text_color(*color)
    pdf.cell(0, 9, f"Résultat : {fmt_eur(resultat)}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(*MUTED)
