"""Budget document builders (PDF + Excel): prévu vs réalisé by category."""

from ..data.budget import BudgetData, BudgetLigneExport
from ..format import fmt_amount, fmt_eur
from ..pdf import DEPENSE, MUTED, RECETTE, AbacusPDF
from ..xlsx import Column, Sheet, workbook_bytes

_HEADERS = ["Catégorie", "Prévu", "Réalisé", "Écart"]
_WIDTHS = (76, 30, 30, 30)
_ALIGNS = ("LEFT", "RIGHT", "RIGHT", "RIGHT")


def _section(
    pdf: AbacusPDF,
    title: str,
    lignes: list[BudgetLigneExport],
    total_prevu,
    total_realise,
) -> None:
    pdf.section_title(title)
    if not lignes:
        pdf.set_font("plex", "", 10)
        pdf.set_text_color(*MUTED)
        pdf.cell(0, 8, "Aucune catégorie.", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)
        pdf.set_text_color(0, 0, 0)
        return
    rows = [
        [
            ligne.libelle,
            fmt_amount(ligne.prevu),
            fmt_amount(ligne.realise),
            fmt_amount(ligne.ecart),
        ]
        for ligne in lignes
    ]
    pdf.table(
        _HEADERS,
        rows,
        widths=_WIDTHS,
        aligns=_ALIGNS,
        total_row=[
            "Total",
            fmt_amount(total_prevu),
            fmt_amount(total_realise),
            fmt_amount(total_realise - total_prevu),
        ],
    )
    pdf.ln(3)


def budget_pdf(association_name: str, data: BudgetData) -> bytes:
    pdf = AbacusPDF(
        association_name=association_name,
        title="Budget",
        subtitle=f"Exercice {data.exercice_libelle}",
    )
    pdf.add_page()
    _section(
        pdf,
        "Recettes",
        data.recettes,
        data.total_recettes_prevu,
        data.total_recettes_realise,
    )
    _section(
        pdf,
        "Dépenses",
        data.depenses,
        data.total_depenses_prevu,
        data.total_depenses_realise,
    )

    pdf.ln(1)
    pdf.set_font("plex", "", 10)
    pdf.set_text_color(*MUTED)
    pdf.cell(
        0,
        7,
        f"Résultat prévisionnel : {fmt_eur(data.resultat_prevu)}",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.set_font("plex", "B", 13)
    pdf.set_text_color(*(RECETTE if data.resultat_realise >= 0 else DEPENSE))
    pdf.cell(
        0,
        9,
        f"Résultat réalisé : {fmt_eur(data.resultat_realise)}",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    return pdf.to_bytes()


def budget_xlsx(data: BudgetData) -> bytes:
    columns = [
        Column("Poste", width=12),
        Column("Catégorie", width=32),
        Column("Prévu", "amount"),
        Column("Réalisé", "amount"),
        Column("Écart", "amount"),
    ]
    rows: list[list] = []
    for ligne in data.recettes:
        rows.append(["Recette", ligne.libelle, ligne.prevu, ligne.realise, ligne.ecart])
    for ligne in data.depenses:
        rows.append(["Dépense", ligne.libelle, ligne.prevu, ligne.realise, ligne.ecart])
    return workbook_bytes([Sheet(title="Budget", columns=columns, rows=rows)])
