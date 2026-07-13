"""Chart-of-accounts rules: numbering, coherence and archiving guards.

Pure-ish helpers (session in, no commit) so the routes stay a thin transport
layer. Every rule here protects the ledger: a number is a permanent reference
(entries, balance, FEC), an account's classe drives the bilan/résultat split,
and the engine hard-depends on a handful of ANC accounts.
"""

import re

from sqlmodel import Session, select

from accounting_engine import (
    CLASSE_CHARGE,
    CLASSE_PRODUIT,
    COMPTE_REPORT_CREDITEUR,
    COMPTE_REPORT_DEBITEUR,
    COMPTE_RESERVES,
    COMPTE_RESULTAT_DEFICIT,
    COMPTE_RESULTAT_EXCEDENT,
    COMPTE_TVA_A_DECAISSER,
    COMPTE_TVA_COLLECTEE,
    COMPTE_TVA_DEDUCTIBLE,
    PREFIXE_BANQUE,
    PREFIXE_CAISSE,
)
from http_errors import bad_request, conflict
from models import CategorieSaisie, Compte, CompteType

# A well-formed account number: a classe (1–8) then 1–6 more digits ("61", "6135").
_NUMERO_RE = re.compile(r"^[1-8][0-9]{1,6}$")

# Accounts the engine posts to by number: closing (report à nouveau, résultat,
# réserves) and VAT. Archiving one would break the closing or the VAT split.
STRUCTURAL_NUMEROS: frozenset[str] = frozenset(
    {
        COMPTE_RESERVES,
        COMPTE_REPORT_CREDITEUR,
        COMPTE_REPORT_DEBITEUR,
        COMPTE_RESULTAT_EXCEDENT,
        COMPTE_RESULTAT_DEFICIT,
        COMPTE_TVA_COLLECTEE,
        COMPTE_TVA_DEDUCTIBLE,
        COMPTE_TVA_A_DECAISSER,
    }
)

# Numbers reserved for named treasury accounts (§15.4): they carry a type, an
# IBAN and a colour, so they are created and archived from Trésorerie.
TREASURY_PREFIXES: tuple[str, ...] = (PREFIXE_BANQUE, PREFIXE_CAISSE)

_TRESORERIE_MSG = (
    "Ce compte est un compte de trésorerie : il se gère depuis la page Trésorerie."
)

# Which natures a classe may carry. Charges and produits are pinned (they drive
# the compte de résultat); balance-sheet classes accept either side; class 8
# (contributions volontaires en nature) mirrors the résultat.
_TYPES_PAR_CLASSE: dict[int, frozenset[CompteType]] = {
    1: frozenset({CompteType.ACTIF, CompteType.PASSIF}),
    2: frozenset({CompteType.ACTIF, CompteType.PASSIF}),
    3: frozenset({CompteType.ACTIF, CompteType.PASSIF}),
    4: frozenset({CompteType.ACTIF, CompteType.PASSIF}),
    5: frozenset({CompteType.ACTIF, CompteType.PASSIF}),
    CLASSE_CHARGE: frozenset({CompteType.CHARGE}),
    CLASSE_PRODUIT: frozenset({CompteType.PRODUIT}),
    8: frozenset({CompteType.CHARGE, CompteType.PRODUIT}),
}


def is_treasury_numero(numero: str) -> bool:
    return numero.startswith(TREASURY_PREFIXES)


def validate_numero(numero: str) -> int:
    """Return the classe of a well-formed account number, or raise 400."""
    if not _NUMERO_RE.match(numero):
        raise bad_request(
            "Un numéro de compte commence par sa classe (1 à 8) et compte au "
            "moins deux chiffres (ex. 6135)."
        )
    return int(numero[0])


def validate_type(classe: int, type_: CompteType) -> None:
    attendus = _TYPES_PAR_CLASSE[classe]
    if type_ not in attendus:
        libelles = " ou ".join(sorted(t.value for t in attendus))
        raise bad_request(
            f"Un compte de classe {classe} doit être de nature {libelles}."
        )


def next_numero(session: Session, association_id: str, prefixe: str) -> str:
    """First free ``{prefixe}{n}`` (n ≥ 1) in the association's chart of accounts.

    Same rule as the treasury numbering: the rubrique itself (606) is taken, its
    children get readable sub-numbers (6061, 6062…).
    """
    validate_numero(prefixe)
    taken = set(
        session.exec(
            select(Compte.numero).where(
                Compte.association_id == association_id,
                Compte.numero.startswith(prefixe),
            )
        ).all()
    )
    n = 1
    while f"{prefixe}{n}" in taken:
        n += 1
    return f"{prefixe}{n}"


def numero_taken(session: Session, association_id: str, numero: str) -> bool:
    return (
        session.exec(
            select(Compte.id).where(
                Compte.association_id == association_id, Compte.numero == numero
            )
        ).first()
        is not None
    )


def guard_not_treasury(compte: Compte) -> None:
    """Treasury accounts are managed from Trésorerie (one path, one rule set)."""
    if compte.type_tresorerie is not None:
        raise conflict(_TRESORERIE_MSG)


def guard_treasury_numero(numero: str) -> None:
    if is_treasury_numero(numero):
        raise conflict(
            "Les comptes 512x / 531x sont des comptes de trésorerie : "
            "créez-les depuis la page Trésorerie."
        )


def guard_archivable(session: Session, association_id: str, compte: Compte) -> None:
    """Refuse archiving an account the app still depends on.

    Archiving is never destructive (entries keep their ``compte_id``), but an
    account the engine posts to — or that an active category points at — must stay
    selectable, otherwise the next closing or the next saisie fails.
    """
    if compte.numero in STRUCTURAL_NUMEROS:
        raise conflict(
            "Ce compte est structurant (clôture, TVA) : il ne peut pas être archivé."
        )
    categorie = session.exec(
        select(CategorieSaisie.libelle).where(
            CategorieSaisie.association_id == association_id,
            CategorieSaisie.compte_id == compte.id,
            CategorieSaisie.is_active.is_(True),
        )
    ).first()
    if categorie is not None:
        raise conflict(
            f"La catégorie « {categorie} » utilise ce compte : archivez-la d'abord."
        )
