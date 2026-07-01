import uuid
from datetime import date
from decimal import Decimal
from enum import Enum

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class CompteType(str, Enum):
    """Balance-sheet vs. income-statement nature of an account.

    Drives the bilan / compte de résultat classification. Stable strings.
    """

    ACTIF = "actif"
    PASSIF = "passif"
    CHARGE = "charge"
    PRODUIT = "produit"


class ExerciceStatut(str, Enum):
    OUVERT = "ouvert"
    CLOTURE = "cloture"


class TypeTresorerie(str, Enum):
    """Kind of a *named treasury account* (§15.4), surfaced to the treasurer.

    Drives the default ANC account prefix (caisse -> 531x, otherwise -> 512x)
    and the grouping/icon in the UI. A ``Compte`` carries this only when it is a
    treasury account; ordinary chart-of-accounts lines leave it null. Stable
    strings (persisted).
    """

    BANQUE = "banque"
    CAISSE = "caisse"
    EN_LIGNE = "en_ligne"  # HelloAsso, Cagnotte…
    EPARGNE = "epargne"
    AUTRE = "autre"


class Compte(SQLModel, table=True):
    __tablename__ = "compte"
    # An account number is unique within an association's chart of accounts.
    __table_args__ = (
        UniqueConstraint("association_id", "numero", name="uq_compte_assoc_numero"),
    )

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    association_id: str = Field(foreign_key="association.id", index=True)
    numero: str = Field(index=True)  # e.g. "512", "756"
    libelle: str
    classe: int  # 1..8 (= int(numero[0]))
    type: CompteType
    is_active: bool = Field(default=True)
    # Treasury metadata — set only on named treasury accounts (§15.4); a null
    # ``type_tresorerie`` marks an ordinary chart-of-accounts line. The current
    # balance is never stored: it is computed from the ledger (grand livre).
    type_tresorerie: TypeTresorerie | None = Field(default=None, index=True)
    iban: str | None = None  # IBAN (banque) or platform identifier (en_ligne)
    couleur: str | None = None  # UI accent, e.g. "#2563EB"
    ordre: int = Field(default=0)  # display order among treasury accounts


class Journal(SQLModel, table=True):
    __tablename__ = "journal"
    __table_args__ = (
        UniqueConstraint("association_id", "code", name="uq_journal_assoc_code"),
    )

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    association_id: str = Field(foreign_key="association.id", index=True)
    code: str  # BQ, CA, AC, VE, OD
    libelle: str


class Exercice(SQLModel, table=True):
    __tablename__ = "exercice"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    association_id: str = Field(foreign_key="association.id", index=True)
    libelle: str  # e.g. "2026"
    date_debut: date
    date_fin: date
    statut: ExerciceStatut = Field(default=ExerciceStatut.OUVERT)
    report_a_nouveau_genere: bool = Field(default=False)


class CompteRead(SQLModel):
    id: str
    numero: str
    libelle: str
    classe: int
    type: CompteType
    is_active: bool


class CompteTresorerieRead(SQLModel):
    """A named treasury account with its current balance (computed from the ledger)."""

    id: str
    numero: str
    libelle: str
    type_tresorerie: TypeTresorerie
    iban: str | None
    couleur: str | None
    ordre: int
    is_active: bool
    solde: Decimal  # débit − crédit cumulé (positif = disponibilités)


class JournalRead(SQLModel):
    id: str
    code: str
    libelle: str


class ExerciceRead(SQLModel):
    id: str
    libelle: str
    date_debut: date
    date_fin: date
    statut: ExerciceStatut
    report_a_nouveau_genere: bool


class ExerciceCreate(SQLModel):
    """Body to open a new fiscal year (dates are parametric — shifted years OK)."""

    libelle: str
    date_debut: date
    date_fin: date


class AffectationResultat(SQLModel):
    """How the exercice result is affected at closing (plan §6, decision d'AG).

    Both amounts are non-negative and sum to the absolute result: the report à
    nouveau share (110 excédent / 119 déficit) and the reserves share (106).
    """

    report_a_nouveau: Decimal
    reserves: Decimal = Decimal("0")


class ClotureResult(SQLModel):
    """Outcome of a closing: the result, its affectation and both fiscal years."""

    resultat: Decimal
    report_a_nouveau: Decimal
    reserves: Decimal
    exercice_cloture: ExerciceRead
    exercice_suivant: ExerciceRead
