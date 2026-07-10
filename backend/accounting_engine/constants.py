"""Domain constants: the single source of truth for the ANC account roles,
journal codes and accounting-class ranges the engine and its callers depend on.

Before this module these facts lived as ad-hoc literals redeclared in each router
(``"110"`` here, ``_COLLECTEE = "44571"`` there, ``[6, 7]`` inline elsewhere), so a
plan-comptable change had to be chased through ~10 files and could silently
diverge. Import the named roles from here instead.
"""

from decimal import Decimal

CENTS = Decimal("0.01")
ZERO = Decimal("0.00")


def to_decimal(value) -> Decimal:
    """Coerce a SQL ``SUM``/``COALESCE`` result to :class:`~decimal.Decimal`.

    The DB driver returns aggregates as ``str`` or ``int`` depending on the
    backend; ``None`` (no rows) reads as zero. Replaces the ``Decimal(str(x))``
    idiom that was reinvented across the services.
    """
    return Decimal(str(value)) if value is not None else ZERO


# --- ANC account roles (numéros de comptes à sémantique fixe) -----------------
# Fonds propres / affectation du résultat
COMPTE_RESERVES = "106"
COMPTE_REPORT_CREDITEUR = "110"  # report à nouveau, solde créditeur
COMPTE_REPORT_DEBITEUR = "119"  # report à nouveau, solde débiteur
COMPTE_RESULTAT_EXCEDENT = "120"
COMPTE_RESULTAT_DEFICIT = "129"
PREFIXE_RESULTAT = "12"  # comptes de résultat (12x), hors report à nouveau
# TVA
COMPTE_TVA_COLLECTEE = "44571"
COMPTE_TVA_DEDUCTIBLE = "44566"
COMPTE_TVA_A_DECAISSER = "44551"
# Préfixes de trésorerie
PREFIXE_BANQUE = "512"  # banque, en ligne, épargne, autre
PREFIXE_CAISSE = "531"  # caisse (espèces)

# --- Codes journaux (cf. accounting_seed.DEFAULT_JOURNALS) --------------------
JOURNAL_BANQUE = "BQ"
JOURNAL_CAISSE = "CA"
JOURNAL_ACHATS = "AC"
JOURNAL_VENTES = "VE"
JOURNAL_DIVERS = "OD"  # opérations diverses (à-nouveau, clôture, report)

# --- Plages de classes comptables --------------------------------------------
CLASSE_CHARGE = 6
CLASSE_PRODUIT = 7
CLASSE_TRESORERIE = 5
CLASSES_GESTION = (CLASSE_CHARGE, CLASSE_PRODUIT)  # compte de résultat
CLASSES_BILAN = (1, 2, 3, 4, 5)  # bilan (report à nouveau)
