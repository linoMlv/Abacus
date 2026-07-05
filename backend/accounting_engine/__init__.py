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
from .constants import CENTS, ZERO
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
    "ZERO",
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
