"""Document builders: turn gathered data into PDF / Excel bytes."""

from .data import (
    AnnexeData,
    BilanData,
    CompteResultatData,
    EvenementBilanData,
    GrandLivreData,
    JournalData,
    LigneCompte,
    ReleveData,
)
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


# --- Compte de résultat & Bilan ANC (PDF) -----------------------------------

_COMPTE_HEADERS = ["Compte", "Libellé", "Montant"]
_COMPTE_WIDTHS = (22, 64, 28)
_COMPTE_ALIGNS = ("LEFT", "LEFT", "RIGHT")


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


# --- Annexe ANC (PDF) -------------------------------------------------------


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


# --- Bilan d'un événement (PDF) ---------------------------------------------


def _opt_eur(value) -> str:
    return fmt_eur(value) if value is not None else "—"


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
