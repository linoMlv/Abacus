"""Default accounting referential seeded when an association is created.

A curated chart of accounts for the French associative sector (ANC 2018-06):
fonds propres, fonds dédiés, the usual third parties, VAT, charges and produits
with the association specifics (756 Cotisations, 754 Dons, 74 Subventions), plus
class 8 contributions volontaires en nature.

This is a pragmatic starter set, not the exhaustive plan — it is meant to be
extended per association and reviewed by an accountant. Accounts are inactive
to start being possible later; here they all seed active.
"""

from datetime import date

from models import (
    Compte,
    CompteType,
    Exercice,
    ExerciceStatut,
    Journal,
)

A = CompteType.ACTIF
P = CompteType.PASSIF
C = CompteType.CHARGE
R = CompteType.PRODUIT

# Default journals (code, libellé).
DEFAULT_JOURNALS: list[tuple[str, str]] = [
    ("BQ", "Banque"),
    ("CA", "Caisse"),
    ("AC", "Achats"),
    ("VE", "Ventes / Recettes"),
    ("OD", "Opérations diverses"),
]

# Chart of accounts: (numéro, libellé, nature). classe = int(numéro[0]).
PLAN_COMPTABLE_ANC: list[tuple[str, str, CompteType]] = [
    # Classe 1 — Fonds propres, provisions, fonds dédiés, emprunts
    ("102", "Fonds propres sans droit de reprise", P),
    ("106", "Réserves", P),
    ("110", "Report à nouveau (solde créditeur)", P),
    ("119", "Report à nouveau (solde débiteur)", P),
    ("120", "Résultat de l'exercice (excédent)", P),
    ("129", "Résultat de l'exercice (déficit)", P),
    ("131", "Subventions d'investissement", P),
    ("151", "Provisions pour risques", P),
    ("164", "Emprunts auprès des établissements de crédit", P),
    ("1951", "Fonds dédiés sur subventions de fonctionnement", P),
    ("1952", "Fonds dédiés sur dons manuels affectés", P),
    # Classe 2 — Immobilisations
    ("205", "Concessions, brevets, licences, logiciels", A),
    ("211", "Terrains", A),
    ("213", "Constructions", A),
    ("215", "Installations techniques, matériel et outillage", A),
    ("2183", "Matériel de bureau et informatique", A),
    ("2184", "Mobilier", A),
    ("281", "Amortissements des immobilisations", A),
    # Classe 4 — Tiers
    ("401", "Fournisseurs", P),
    ("411", "Usagers, adhérents et clients", A),
    ("421", "Personnel - rémunérations dues", P),
    ("431", "Sécurité sociale", P),
    ("44566", "TVA déductible sur autres biens et services", A),
    ("44571", "TVA collectée", P),
    ("44551", "TVA à décaisser", P),
    ("468", "Charges à payer et produits à recevoir", P),
    # Classe 5 — Comptes financiers
    ("512", "Banque", A),
    ("514", "Chèques postaux", A),
    ("531", "Caisse", A),
    ("580", "Virements internes", A),
    # Classe 6 — Charges
    ("6063", "Fournitures d'entretien et petit équipement", C),
    ("6064", "Fournitures administratives", C),
    ("6068", "Autres achats", C),
    ("611", "Sous-traitance générale", C),
    ("613", "Locations", C),
    ("615", "Entretien et réparations", C),
    ("616", "Primes d'assurance", C),
    ("618", "Documentation", C),
    ("622", "Rémunérations d'intermédiaires et honoraires", C),
    ("623", "Publicité, publications, relations publiques", C),
    ("625", "Déplacements, missions et réceptions", C),
    ("626", "Frais postaux et de télécommunications", C),
    ("627", "Services bancaires et assimilés", C),
    ("6281", "Cotisations versées à d'autres organismes", C),
    ("641", "Rémunérations du personnel", C),
    ("645", "Charges de sécurité sociale et de prévoyance", C),
    ("658", "Charges diverses de gestion courante", C),
    ("671", "Charges exceptionnelles", C),
    ("681", "Dotations aux amortissements et provisions", C),
    ("689", "Engagements à réaliser sur ressources affectées", C),
    # Classe 7 — Produits
    ("706", "Prestations de services", R),
    ("707", "Ventes de marchandises", R),
    ("708", "Produits des activités annexes", R),
    ("740", "Subventions d'exploitation", R),
    ("7541", "Dons manuels", R),
    ("7542", "Mécénat", R),
    ("756", "Cotisations", R),
    ("758", "Produits divers de gestion courante", R),
    ("775", "Produits exceptionnels", R),
    ("781", "Reprises sur amortissements et provisions", R),
    ("789", "Report des ressources non utilisées des exercices antérieurs", R),
    # Classe 8 — Contributions volontaires en nature
    ("864", "Personnel bénévole", C),
    ("871", "Prestations en nature", R),
    ("875", "Bénévolat", R),
]


def seed_association_accounting(
    session, association_id: str, year: int | None = None
) -> None:
    """Create the default journals, chart of accounts and current fiscal year.

    Does not commit: the caller commits as part of the association creation
    transaction.
    """
    year = year or date.today().year

    for code, libelle in DEFAULT_JOURNALS:
        session.add(Journal(association_id=association_id, code=code, libelle=libelle))

    for numero, libelle, nature in PLAN_COMPTABLE_ANC:
        session.add(
            Compte(
                association_id=association_id,
                numero=numero,
                libelle=libelle,
                classe=int(numero[0]),
                type=nature,
            )
        )

    session.add(
        Exercice(
            association_id=association_id,
            libelle=str(year),
            date_debut=date(year, 1, 1),
            date_fin=date(year, 12, 31),
            statut=ExerciceStatut.OUVERT,
        )
    )
