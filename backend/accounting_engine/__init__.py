"""Double-entry engine.

Historically a single ``accounting_engine.py`` module. Split by concern
(invariants, numbering, fiscal-year lookups, entry builders, closing) but kept
importable exactly as before (``from accounting_engine import X``) via these
re-exports, so no call site had to change.
"""

from .builders import (
    build_ecriture_a_nouveau,
    build_ecriture_extourne,
    build_ecriture_simple,
    build_ecriture_virement,
)
from .closing import (
    build_ecriture_determination_resultat,
    build_ecriture_report_a_nouveau,
)
from .constants import (
    CENTS,
    CLASSE_CHARGE,
    CLASSE_PRODUIT,
    CLASSE_TRESORERIE,
    CLASSES_BILAN,
    CLASSES_GESTION,
    COMPTE_REPORT_CREDITEUR,
    COMPTE_REPORT_DEBITEUR,
    COMPTE_RESERVES,
    COMPTE_RESULTAT_DEFICIT,
    COMPTE_RESULTAT_EXCEDENT,
    COMPTE_TVA_A_DECAISSER,
    COMPTE_TVA_COLLECTEE,
    COMPTE_TVA_DEDUCTIBLE,
    JOURNAL_ACHATS,
    JOURNAL_BANQUE,
    JOURNAL_CAISSE,
    JOURNAL_DIVERS,
    JOURNAL_VENTES,
    PREFIXE_BANQUE,
    PREFIXE_CAISSE,
    PREFIXE_RESULTAT,
    ZERO,
    to_decimal,
)
from .exercices import (
    find_exercice_covering,
    find_open_exercice,
    resultat_de_gestion,
    scope_exercice,
)
from .invariants import (
    EntryError,
    exclude_cloture,
    validate_lignes,
    validated_only,
)
from .numbering import next_numero_piece
from .tva import split_ttc

__all__ = [
    "CENTS",
    "CLASSE_CHARGE",
    "CLASSE_PRODUIT",
    "CLASSE_TRESORERIE",
    "CLASSES_BILAN",
    "CLASSES_GESTION",
    "COMPTE_REPORT_CREDITEUR",
    "COMPTE_REPORT_DEBITEUR",
    "COMPTE_RESERVES",
    "COMPTE_RESULTAT_DEFICIT",
    "COMPTE_RESULTAT_EXCEDENT",
    "COMPTE_TVA_A_DECAISSER",
    "COMPTE_TVA_COLLECTEE",
    "COMPTE_TVA_DEDUCTIBLE",
    "JOURNAL_ACHATS",
    "JOURNAL_BANQUE",
    "JOURNAL_CAISSE",
    "JOURNAL_DIVERS",
    "JOURNAL_VENTES",
    "PREFIXE_BANQUE",
    "PREFIXE_CAISSE",
    "PREFIXE_RESULTAT",
    "ZERO",
    "to_decimal",
    "EntryError",
    "build_ecriture_a_nouveau",
    "build_ecriture_determination_resultat",
    "build_ecriture_extourne",
    "build_ecriture_report_a_nouveau",
    "build_ecriture_simple",
    "build_ecriture_virement",
    "exclude_cloture",
    "find_exercice_covering",
    "find_open_exercice",
    "next_numero_piece",
    "resultat_de_gestion",
    "scope_exercice",
    "split_ttc",
    "validate_lignes",
    "validated_only",
]
