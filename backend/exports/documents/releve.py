"""Relevé par compte de trésorerie (PDF)."""

from ..data import ReleveData
from ..format import fmt_amount, fmt_date, fmt_eur
from ..pdf import DEPENSE, RECETTE, AbacusPDF
from .common import _amount_or_blank


def releve_pdf(association_name: str, data: ReleveData) -> bytes:
    subtitle = (
        f"{data.compte_numero} · {data.compte_libelle} — "
        f"du {fmt_date(data.date_from)} au {fmt_date(data.date_to)}"
    )
    pdf = AbacusPDF(
        association_name=association_name, title="Relevé de compte", subtitle=subtitle
    )
    pdf.add_page()
    pdf.summary(
        [
            ("Solde initial", fmt_eur(data.solde_initial), None),
            ("Total des débits", fmt_eur(data.total_debit), None),
            ("Total des crédits", fmt_eur(data.total_credit), None),
            (
                "Solde final",
                fmt_eur(data.solde_final),
                RECETTE if data.solde_final >= 0 else DEPENSE,
            ),
        ]
    )

    headers = ["Date", "Pièce", "Journal", "Libellé", "Débit", "Crédit", "Solde"]
    rows = [
        [
            fmt_date(data.date_from),
            "",
            "",
            "Solde initial",
            "",
            "",
            fmt_amount(data.solde_initial),
        ]
    ]
    for m in data.mouvements:
        rows.append(
            [
                fmt_date(m.date),
                str(m.numero_piece),
                m.journal_code,
                m.libelle,
                _amount_or_blank(m.debit),
                _amount_or_blank(m.credit),
                fmt_amount(m.solde),
            ]
        )
    total = [
        "",
        "",
        "",
        "Solde final",
        fmt_amount(data.total_debit),
        fmt_amount(data.total_credit),
        fmt_amount(data.solde_final),
    ]
    pdf.table(
        headers,
        rows,
        widths=(16, 12, 14, 56, 20, 20, 24),
        aligns=("LEFT", "CENTER", "CENTER", "LEFT", "RIGHT", "RIGHT", "RIGHT"),
        total_row=total,
    )
    return pdf.to_bytes()
