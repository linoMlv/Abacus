"""Document builders: turn gathered data into PDF / Excel bytes.

Historically a single ``documents.py`` module, split by report family (relevé,
journal & grand livre, compte de résultat & bilan, annexe, événement) over shared
PDF helpers. Every builder is re-exported so ``documents.<fn>`` call sites are
unchanged.
"""

from .annexe import annexe_pdf
from .evenement import evenement_bilan_pdf
from .journal import (
    grand_livre_pdf,
    grand_livre_xlsx,
    journal_pdf,
    journal_xlsx,
)
from .releve import releve_pdf
from .resultat_bilan import bilan_pdf, compte_resultat_pdf

__all__ = [
    "annexe_pdf",
    "bilan_pdf",
    "compte_resultat_pdf",
    "evenement_bilan_pdf",
    "grand_livre_pdf",
    "grand_livre_xlsx",
    "journal_pdf",
    "journal_xlsx",
    "releve_pdf",
]
