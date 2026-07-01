"""Bilan d'un événement (PDF)."""

from ..data import EvenementBilanData
from ..format import fmt_amount, fmt_date, fmt_eur
from ..pdf import DEPENSE, RECETTE, AbacusPDF
from .common import _amount_or_blank, _empty_note, _opt_eur


def evenement_bilan_pdf(association_name: str, data: EvenementBilanData) -> bytes:
    period = ""
    if data.date_debut or data.date_fin:
        period = f" — du {fmt_date(data.date_debut)} au {fmt_date(data.date_fin)}"
    pdf = AbacusPDF(
        association_name=association_name,
        title="Bilan d'événement",
        subtitle=f"{data.nom}{period}",
    )
    pdf.add_page()
    pdf.summary(
        [
            ("Budget recettes", _opt_eur(data.budget_recettes), None),
            ("Réalisé recettes", fmt_eur(data.realise_recettes), RECETTE),
            ("Budget dépenses", _opt_eur(data.budget_depenses), None),
            ("Réalisé dépenses", fmt_eur(data.realise_depenses), DEPENSE),
            (
                "Résultat",
                fmt_eur(data.resultat),
                RECETTE if data.resultat >= 0 else DEPENSE,
            ),
        ]
    )

    pdf.section_title("Opérations")
    if not data.operations:
        _empty_note(pdf, "Aucune opération rattachée à cet événement.")
        return pdf.to_bytes()

    rows = [
        [
            fmt_date(op.date),
            str(op.numero_piece),
            op.libelle,
            _amount_or_blank(op.recette),
            _amount_or_blank(op.depense),
        ]
        for op in data.operations
    ]
    pdf.table(
        ["Date", "Pièce", "Libellé", "Recette", "Dépense"],
        rows,
        widths=(18, 14, 62, 24, 24),
        aligns=("LEFT", "CENTER", "LEFT", "RIGHT", "RIGHT"),
        total_row=[
            "",
            "",
            "Total",
            fmt_amount(data.realise_recettes),
            fmt_amount(data.realise_depenses),
        ],
    )
    return pdf.to_bytes()
