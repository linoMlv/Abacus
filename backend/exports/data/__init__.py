"""Tenant-scoped data gathering for the exports (queries only, no rendering).

Historically a single ``data.py`` module, split by report family (relevé,
journal/grand livre, compte de résultat, bilan, événement, annexe) over shared
primitives. Every dataclass and gatherer is re-exported so
``from exports.data import X`` call sites are unchanged.
"""

from .annexe import AnnexeData, AnnexeSection, annexe_data
from .bilan import BilanData, bilan_data
from .common import LigneCompte, Mouvement, resolve_period
from .evenement import EvenementBilanData, EvenementOperation, evenement_bilan_data
from .journal import (
    CompteLedger,
    GrandLivreData,
    JournalData,
    JournalLigne,
    grand_livre_data,
    journal_data,
)
from .releve import ReleveData, releve_data
from .resultat import CompteResultatData, compte_resultat_data

__all__ = [
    "AnnexeData",
    "AnnexeSection",
    "BilanData",
    "CompteLedger",
    "CompteResultatData",
    "EvenementBilanData",
    "EvenementOperation",
    "GrandLivreData",
    "JournalData",
    "JournalLigne",
    "LigneCompte",
    "Mouvement",
    "ReleveData",
    "annexe_data",
    "bilan_data",
    "compte_resultat_data",
    "evenement_bilan_data",
    "grand_livre_data",
    "journal_data",
    "releve_data",
    "resolve_period",
]
