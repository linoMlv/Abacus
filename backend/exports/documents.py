"""Document builders: turn gathered data into PDF / Excel bytes."""

from .data import GrandLivreData, JournalData, ReleveData
from .format import fmt_amount, fmt_date, fmt_eur
from .pdf import DEPENSE, MUTED, RECETTE, AbacusPDF
from .xlsx import Column, Sheet, workbook_bytes


def _amount_or_blank(value) -> str:
    return fmt_amount(value) if value else ""


def _period_subtitle(date_from, date_to) -> str:
    return f"Période du {fmt_date(date_from)} au {fmt_date(date_to)}"


def _empty_note(pdf: AbacusPDF, text: str) -> None:
    pdf.set_font("plex", "", 10)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 8, text, new_x="LMARGIN", new_y="NEXT")


# --- Relevé par compte de trésorerie (PDF) ----------------------------------


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


# --- Journal (PDF + Excel) --------------------------------------------------


def journal_pdf(association_name: str, data: JournalData) -> bytes:
    pdf = AbacusPDF(
        association_name=association_name,
        title="Journal",
        subtitle=_period_subtitle(data.date_from, data.date_to),
    )
    pdf.add_page()
    if not data.lignes:
        _empty_note(pdf, "Aucune écriture sur la période.")
        return pdf.to_bytes()

    headers = ["Date", "Pièce", "Jrnl", "Compte", "Libellé", "Débit", "Crédit"]
    rows = []
    for ligne in data.lignes:
        rows.append(
            [
                fmt_date(ligne.date) if ligne.first_of_entry else "",
                str(ligne.numero_piece) if ligne.first_of_entry else "",
                ligne.journal_code if ligne.first_of_entry else "",
                ligne.compte,
                ligne.libelle,
                _amount_or_blank(ligne.debit),
                _amount_or_blank(ligne.credit),
            ]
        )
    total = [
        "",
        "",
        "",
        "",
        "Total",
        fmt_amount(data.total_debit),
        fmt_amount(data.total_credit),
    ]
    pdf.table(
        headers,
        rows,
        widths=(15, 11, 11, 42, 46, 20, 20),
        aligns=("LEFT", "CENTER", "CENTER", "LEFT", "LEFT", "RIGHT", "RIGHT"),
        total_row=total,
    )
    return pdf.to_bytes()


def journal_xlsx(data: JournalData) -> bytes:
    columns = [
        Column("Date", "date", 14),
        Column("Pièce", "text", 8),
        Column("Journal", "text", 10),
        Column("Compte", "text", 32),
        Column("Libellé", "text", 42),
        Column("Débit", "amount", 16),
        Column("Crédit", "amount", 16),
    ]
    rows = [
        [
            ligne.date,
            ligne.numero_piece,
            ligne.journal_code,
            ligne.compte,
            ligne.libelle,
            ligne.debit or None,
            ligne.credit or None,
        ]
        for ligne in data.lignes
    ]
    if data.lignes:
        rows.append(
            [None, None, None, None, "Total", data.total_debit, data.total_credit]
        )
    return workbook_bytes([Sheet("Journal", columns, rows)])


# --- Grand livre (PDF + Excel) ----------------------------------------------


def grand_livre_pdf(association_name: str, data: GrandLivreData) -> bytes:
    pdf = AbacusPDF(
        association_name=association_name,
        title="Grand livre",
        subtitle=_period_subtitle(data.date_from, data.date_to),
    )
    pdf.add_page()
    if not data.comptes:
        _empty_note(pdf, "Aucun mouvement sur la période.")
        return pdf.to_bytes()

    headers = ["Date", "Pièce", "Jrnl", "Libellé", "Débit", "Crédit", "Solde"]
    for ledger in data.comptes:
        pdf.section_title(f"{ledger.numero} · {ledger.libelle}")
        rows = [
            [
                fmt_date(data.date_from),
                "",
                "",
                "Solde initial",
                "",
                "",
                fmt_amount(ledger.solde_initial),
            ]
        ]
        for m in ledger.mouvements:
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
            "Total / solde",
            fmt_amount(ledger.total_debit),
            fmt_amount(ledger.total_credit),
            fmt_amount(ledger.solde_final),
        ]
        pdf.table(
            headers,
            rows,
            widths=(16, 12, 12, 54, 20, 20, 24),
            aligns=("LEFT", "CENTER", "CENTER", "LEFT", "RIGHT", "RIGHT", "RIGHT"),
            total_row=total,
        )
        pdf.ln(5)
    return pdf.to_bytes()


def grand_livre_xlsx(data: GrandLivreData) -> bytes:
    columns = [
        Column("Compte", "text", 30),
        Column("Date", "date", 14),
        Column("Pièce", "text", 8),
        Column("Journal", "text", 10),
        Column("Libellé", "text", 42),
        Column("Débit", "amount", 16),
        Column("Crédit", "amount", 16),
        Column("Solde", "amount", 18),
    ]
    rows = []
    for ledger in data.comptes:
        label = f"{ledger.numero} {ledger.libelle}"
        rows.append(
            [
                label,
                data.date_from,
                None,
                None,
                "Solde initial",
                None,
                None,
                ledger.solde_initial,
            ]
        )
        for m in ledger.mouvements:
            rows.append(
                [
                    label,
                    m.date,
                    m.numero_piece,
                    m.journal_code,
                    m.libelle,
                    m.debit or None,
                    m.credit or None,
                    m.solde,
                ]
            )
    return workbook_bytes([Sheet("Grand livre", columns, rows)])
