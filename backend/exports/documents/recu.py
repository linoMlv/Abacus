"""Donation tax receipt (reçu fiscal) PDF.

A compliant receipt carrying every mandatory legal mention (art. 200 / 238 bis /
978 CGI): the beneficiary association's identity, the donor's identity, the
amount in figures and words, the form and date, the on-honour certification and a
signature area. Rendered with the shared house style (IBM Plex, no system libs).
"""

from ..format import fmt_date, fmt_eur
from ..lettres import montant_en_lettres
from ..pdf import HAIRLINE, INK, INK_SOFT, MUTED, AbacusPDF

_FORME_LABELS = {
    "numeraire": "Numéraire",
    "titres": "Titres de sociétés",
    "autre": "Autre (abandon de frais, don en nature…)",
}
_MODE_LABELS = {
    "carte": "Carte bancaire",
    "cheque": "Chèque",
    "especes": "Espèces",
    "virement": "Virement",
    "prelevement": "Prélèvement",
    "autre": "Autre",
}


def _identity_block(pdf: AbacusPDF, title: str, lines: list[str]) -> None:
    pdf.set_font("plex", "B", 9)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 5, title.upper(), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("plex", "", 10)
    pdf.set_text_color(*INK)
    for line in lines:
        if line:
            pdf.cell(0, 5.5, line, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)


def _paragraph(
    pdf: AbacusPDF, text: str, *, bold: bool = False, size: int = 10
) -> None:
    pdf.set_font("plex", "B" if bold else "", size)
    pdf.set_text_color(*INK)
    pdf.multi_cell(0, 5.5, text, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)


def recu_pdf(*, association, tiers, recu) -> bytes:
    """Render the receipt for ``recu`` (donor ``tiers``, beneficiary association)."""
    pdf = AbacusPDF(
        association_name=association.name,
        title="Reçu au titre des dons",
        subtitle="Articles 200, 238 bis et 978 du Code général des impôts",
    )
    pdf.add_page()

    pdf.set_font("plex", "B", 11)
    pdf.set_text_color(*INK)
    pdf.cell(0, 7, f"Reçu n° {recu.numero}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("plex", "", 9)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 5, f"Année du versement : {recu.annee}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    ident_lines = [association.name]
    if association.adresse:
        ident_lines.append(association.adresse)
    cp_ville = " ".join(x for x in (association.code_postal, association.ville) if x)
    if cp_ville:
        ident_lines.append(cp_ville)
    numeros = []
    if association.rna:
        numeros.append(f"RNA : {association.rna}")
    if association.siret:
        numeros.append(f"SIRET : {association.siret}")
    if numeros:
        ident_lines.append(" — ".join(numeros))
    if association.objet:
        ident_lines.append(f"Objet : {association.objet}")
    _identity_block(pdf, "Bénéficiaire du don", ident_lines)

    donor_lines = [tiers.nom]
    if tiers.adresse:
        donor_lines.append(tiers.adresse)
    donor_cp_ville = " ".join(x for x in (tiers.code_postal, tiers.ville) if x)
    if donor_cp_ville:
        donor_lines.append(donor_cp_ville)
    _identity_block(pdf, "Donateur", donor_lines)

    pdf.set_draw_color(*HAIRLINE)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(4)

    _paragraph(
        pdf,
        "L'organisme bénéficiaire reconnaît avoir reçu, au titre des dons et "
        "versements ouvrant droit à réduction d'impôt, la somme de :",
    )
    pdf.set_font("plex", "B", 15)
    pdf.set_text_color(*INK)
    pdf.cell(0, 9, fmt_eur(recu.montant), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("plex", "", 10)
    pdf.set_text_color(*INK_SOFT)
    pdf.multi_cell(
        0,
        5.5,
        f"Soit, en toutes lettres : {montant_en_lettres(recu.montant)}.",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(3)

    forme = _FORME_LABELS.get(recu.forme.value, recu.forme.value)
    pdf.summary(
        [
            ("Forme du don", forme, None),
            *(
                [
                    (
                        "Mode de versement",
                        _MODE_LABELS.get(recu.mode_reglement.value, "—"),
                        None,
                    )
                ]
                if recu.mode_reglement
                else []
            ),
            ("Date du reçu", fmt_date(recu.date), None),
        ]
    )

    _paragraph(
        pdf,
        "Le bénéficiaire certifie sur l'honneur que les dons et versements qu'il "
        "reçoit ouvrent droit à la réduction d'impôt prévue aux articles 200, "
        "238 bis et 978 du Code général des impôts.",
        size=9,
    )
    pdf.ln(6)

    ville = association.ville or ""
    pdf.set_font("plex", "", 10)
    pdf.set_text_color(*INK)
    lieu_date = (
        f"Fait à {ville}, le {fmt_date(recu.date)}."
        if ville
        else (f"Fait le {fmt_date(recu.date)}.")
    )
    pdf.cell(0, 6, lieu_date, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_text_color(*MUTED)
    pdf.set_font("plex", "", 9)
    pdf.cell(0, 5, "Signature du responsable habilité :", new_x="LMARGIN", new_y="NEXT")

    return pdf.to_bytes()
