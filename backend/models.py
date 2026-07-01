import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Association(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    name: str = Field(unique=True)
    email: str = Field(unique=True)
    password: str


class RefreshSession(SQLModel, table=True):
    __tablename__ = "refresh_session"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    # Exactly one of association_id (legacy) / user_id (V3) identifies the owner.
    association_id: str | None = Field(default=None, foreign_key="association.id")
    user_id: str | None = Field(default=None, foreign_key="user.id", index=True)
    token_hash: str = Field(unique=True, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime
    revoked_at: datetime | None = None
    user_agent: str | None = None
    ip_address: str | None = None


class LogEntry(SQLModel, table=True):
    __tablename__ = "log_entry"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)
    method: str
    path: str
    status_code: int = 0
    ip_address: str | None = None
    user_agent: str | None = None
    user: str | None = None
    # Association targeted by the request (parsed from /api/asso/{id}/...), so
    # an admin can read the logs scoped to their own association. Plain string
    # (no FK): logging must never fail on an arbitrary/garbage path id.
    association_id: str | None = Field(default=None, index=True)
    duration_ms: float | None = None
    event_type: str | None = None
    detail: str | None = None


class LogEntryRead(SQLModel):
    id: str
    timestamp: datetime
    method: str
    path: str
    status_code: int
    ip_address: str | None
    user_agent: str | None
    user: str | None
    association_id: str | None
    duration_ms: float | None
    event_type: str | None
    detail: str | None


class AuditLog(SQLModel, table=True):
    """Tamper-evidence trail of sensitive actions (who did what, when).

    Distinct from the HTTP ``LogEntry``: this records business actions (entry
    created/validated/deleted, …) for accounting integrity (plan §10). Scoped by
    ``association_id`` so an admin only ever reads their own tenant's trail.
    """

    __tablename__ = "audit_log"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    timestamp: datetime = Field(default_factory=_utcnow, index=True)
    association_id: str | None = Field(
        default=None, foreign_key="association.id", index=True
    )
    actor_user_id: str | None = Field(default=None, foreign_key="user.id")
    action: str = Field(index=True)  # e.g. "ecriture.validate"
    target_type: str | None = None  # e.g. "ecriture"
    target_id: str | None = None
    detail: str | None = None


class AuditLogRead(SQLModel):
    id: str
    timestamp: datetime
    actor_user_id: str | None
    action: str
    target_type: str | None
    target_id: str | None
    detail: str | None


# ---------------------------------------------------------------------------
# Identity & access (V3 multi-association, RBAC)
#
# A User is a physical person with a single global identity. Access to an
# association is granted exclusively through a Membership, which also carries
# the Role. The same person can therefore hold different roles across several
# associations. The role/permission mapping lives in ``authz.py``.
# ---------------------------------------------------------------------------


class Role(str, Enum):
    """Role held by a user *within a given association* (carried by Membership).

    Values are stable strings: they are persisted and may appear in audit
    trails and exports — do not rename them.
    """

    ADMIN = "admin"  # administre l'asso : membres, paramètres, logs (superset)
    ACCOUNTANT = "accountant"  # expert-comptable : saisie manuelle, validation, clôture
    TREASURER = "treasurer"  # trésorier : saisie assistée, banque, dons, budget
    VIEWER = "viewer"  # président / CA : consultation seule


class MembershipStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"  # accès gelé sans suppression (révocable)


class User(SQLModel, table=True):
    __tablename__ = "user"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    # Stored normalized (lowercased) by the auth layer; unique identity key.
    email: str = Field(unique=True, index=True)
    password: str
    name: str
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=_utcnow)


class Membership(SQLModel, table=True):
    __tablename__ = "membership"
    # A user holds at most one membership (and thus one role) per association.
    __table_args__ = (
        UniqueConstraint("user_id", "association_id", name="uq_membership_user_assoc"),
    )

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    association_id: str = Field(foreign_key="association.id", index=True)
    role: Role
    status: MembershipStatus = Field(default=MembershipStatus.ACTIVE)
    invited_by: str | None = Field(default=None, foreign_key="user.id")
    created_at: datetime = Field(default_factory=_utcnow)
    # Fine-grained access (T8): an optional custom preset that replaces the role's
    # permission base, plus a per-member ``{permission_value: bool}`` override map
    # (grant=True / revoke=False). Effective permissions are computed server-side
    # in ``authz.effective_permissions`` (ADMIN stays immune). Cf. plan §2/§15.10.
    preset_id: str | None = Field(
        default=None, foreign_key="permission_preset.id", index=True
    )
    permission_overrides: dict[str, bool] = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False)
    )


class PermissionPreset(SQLModel, table=True):
    """A reusable, association-owned named permission set (custom role, T8).

    Assigned to a ``Membership`` via ``preset_id`` to replace the built-in role's
    permission base; per-member overrides then refine it. Tenant-scoped; its name
    is unique per association. ``permissions`` holds stable permission *values*
    (``domain:action``); unknown values are ignored when computing effective sets.
    """

    __tablename__ = "permission_preset"
    __table_args__ = (
        UniqueConstraint("association_id", "nom", name="uq_preset_assoc_nom"),
    )

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    association_id: str = Field(foreign_key="association.id", index=True)
    nom: str
    permissions: list[str] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False)
    )
    created_at: datetime = Field(default_factory=_utcnow)


class Invitation(SQLModel, table=True):
    __tablename__ = "invitation"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    association_id: str = Field(foreign_key="association.id", index=True)
    # Normalized (lowercased) target email; a User may not exist yet.
    email: str = Field(index=True)
    role: Role
    # Only the hash of the invitation token is stored, never the raw token.
    token_hash: str = Field(unique=True, index=True)
    invited_by: str = Field(foreign_key="user.id")
    created_at: datetime = Field(default_factory=_utcnow)
    expires_at: datetime
    accepted_at: datetime | None = None


class MembershipRead(SQLModel):
    id: str
    association_id: str
    role: Role
    status: MembershipStatus


# ---------------------------------------------------------------------------
# Accounting referential (V3 — plan comptable associatif ANC 2018-06)
#
# Each association owns its own chart of accounts (Compte), journals (Journal)
# and fiscal years (Exercice), seeded at creation. Everything is tenant-scoped
# by association_id; see ``accounting_seed.py`` for the default data.
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Double-entry bookkeeping (V3 — partie double)
#
# An Ecriture is an accounting voucher (pièce comptable) belonging to one
# association, fiscal year (Exercice) and journal. It carries two or more
# LigneEcriture rows whose debits and credits must balance exactly
# (Σ débit = Σ crédit). Validated entries become immutable and closed fiscal
# years are locked — those guarantees are enforced by the service/endpoint
# layers; the balance invariant itself lives in ``accounting_engine.py``.
# ---------------------------------------------------------------------------


class EcritureStatut(str, Enum):
    """Lifecycle of an accounting entry. Stable strings (persisted, audited)."""

    BROUILLON = "brouillon"  # éditable
    VALIDEE = "validee"  # immuable ; modification via contre-passation seulement


class EcritureOrigine(str, Enum):
    """How an entry was produced. Stable strings (persisted, audited)."""

    SAISIE_SIMPLE = "saisie_simple"  # via le moteur recette/dépense assisté
    MANUELLE = "manuelle"  # saisie expert multi-lignes
    VIREMENT = "virement"  # virement interne entre deux comptes de trésorerie
    IMPORT = "import"  # rapprochement bancaire
    RECURRENCE = "recurrence"  # générée par une Recurrence
    A_NOUVEAU = "a_nouveau"  # solde initial d'un compte de trésorerie (§15.4)
    EXTOURNE = "extourne"  # contre-passation d'une écriture validée (§10)


class ModeReglement(str, Enum):
    """How money changed hands — purely informative (§15.3). Stable strings."""

    CARTE = "carte"
    CHEQUE = "cheque"
    ESPECES = "especes"
    VIREMENT = "virement"
    PRELEVEMENT = "prelevement"
    AUTRE = "autre"


class Ecriture(SQLModel, table=True):
    __tablename__ = "ecriture"
    # Voucher numbers are unique and gapless per association (FEC requirement);
    # uniqueness is enforced here, gaplessness by the sequential generator.
    __table_args__ = (
        UniqueConstraint(
            "association_id", "numero_piece", name="uq_ecriture_assoc_piece"
        ),
    )

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    association_id: str = Field(foreign_key="association.id", index=True)
    exercice_id: str = Field(foreign_key="exercice.id", index=True)
    journal_id: str = Field(foreign_key="journal.id", index=True)
    # Plain-language category used by the assisted screen (null on manual entries),
    # memorised for "by category" views. The accounting truth stays on the lines.
    categorie_id: str | None = Field(
        default=None, foreign_key="categorie_saisie.id", index=True
    )
    # Optional third party the operation is with (supplier, donor…), memorised
    # for "by tiers" views. Informative only — the accounting truth is on lines.
    tiers_id: str | None = Field(default=None, foreign_key="tiers.id", index=True)
    # Optional event this operation is part of (analytic axis, §15.6).
    evenement_id: str | None = Field(
        default=None, foreign_key="evenement.id", index=True
    )
    date: date
    numero_piece: int  # séquentiel sans trou par association
    libelle: str
    # Optional "Avancé" metadata, purely informative (§15.3) — never affects the
    # accounting: external reference (supplier invoice n°…) and payment method.
    reference_externe: str | None = None
    mode_reglement: ModeReglement | None = None
    statut: EcritureStatut = Field(default=EcritureStatut.BROUILLON)
    origine: EcritureOrigine
    # When this entry is the contre-passation (extourne) of another, the id of the
    # entry it reverses. Set only on EXTOURNE entries; preserves the audit trail
    # of a correction (the original stays, nothing is silently edited — plan §10).
    extourne_de_id: str | None = Field(
        default=None, foreign_key="ecriture.id", index=True
    )
    created_by: str | None = Field(default=None, foreign_key="user.id")
    created_at: datetime = Field(default_factory=_utcnow)
    validated_by: str | None = Field(default=None, foreign_key="user.id")
    validated_at: datetime | None = None

    lignes: list["LigneEcriture"] = Relationship(
        back_populates="ecriture",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class LigneEcriture(SQLModel, table=True):
    __tablename__ = "ligne_ecriture"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    ecriture_id: str = Field(foreign_key="ecriture.id", index=True)
    compte_id: str = Field(foreign_key="compte.id", index=True)
    libelle: str
    # Each line carries an amount on exactly one side; both are non-negative and
    # exactly one is strictly positive (validated in ``accounting_engine.py``).
    debit: Decimal = Field(default=0, max_digits=10, decimal_places=2)
    credit: Decimal = Field(default=0, max_digits=10, decimal_places=2)

    ecriture: Ecriture | None = Relationship(back_populates="lignes")


# ---------------------------------------------------------------------------
# Assisted entry (saisie simple → partie double)
#
# A CategorieSaisie is the bridge between the plain "recette / dépense" wording
# a volunteer understands and the underlying chart of accounts. It pins the
# produit (recette) or charge (dépense) account and a default journal; the
# counterpart cash account (512 banque / 531 caisse) is chosen per entry by the
# user. Seeded at association creation; see ``accounting_seed.py``.
# ---------------------------------------------------------------------------


class SensCategorie(str, Enum):
    """Direction of an assisted entry. Stable strings (persisted, audited)."""

    RECETTE = "recette"
    DEPENSE = "depense"


class CategorieSaisie(SQLModel, table=True):
    __tablename__ = "categorie_saisie"
    __table_args__ = (
        UniqueConstraint(
            "association_id", "libelle", name="uq_categorie_assoc_libelle"
        ),
    )

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    association_id: str = Field(foreign_key="association.id", index=True)
    sens: SensCategorie
    libelle: str  # parlant : "Cotisations", "Achats de fournitures", "Dons"
    compte_id: str = Field(foreign_key="compte.id")  # produit (recette) / charge
    journal_id: str = Field(foreign_key="journal.id")  # journal par défaut
    is_active: bool = Field(default=True)
    ordre: int = Field(default=0)  # ordre d'affichage dans l'écran de saisie


class TypeTiers(str, Enum):
    """Kind of third party (§3). Stable strings (persisted, audited)."""

    FOURNISSEUR = "fournisseur"
    CLIENT = "client"  # usagers, adhérents, clients
    DONATEUR = "donateur"
    FINANCEUR = "financeur"  # subventions, mécénat
    AUTRE = "autre"


class Tiers(SQLModel, table=True):
    """A third party the association deals with (supplier, member, donor…).

    A lightweight informative entity for now: a name and a type, attached to an
    entry to enable "by tiers" views. The accounting third-party ledger (401/411
    linkage, lettrage) is a later concern.
    """

    __tablename__ = "tiers"
    __table_args__ = (
        UniqueConstraint("association_id", "nom", name="uq_tiers_assoc_nom"),
    )

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    association_id: str = Field(foreign_key="association.id", index=True)
    type: TypeTiers
    nom: str
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=_utcnow)


class TiersRead(SQLModel):
    id: str
    type: TypeTiers
    nom: str
    is_active: bool


class EvenementStatut(str, Enum):
    """Lifecycle of an event. Stable strings (persisted, audited)."""

    ACTIF = "actif"
    CLOTURE = "cloture"


class Evenement(SQLModel, table=True):
    """An analytic axis (§15.6): an action/project (Gala 2026…) tagging entries.

    Groups the recettes and dépenses of an action, independently of the chart of
    accounts, so its result (Σ produits − Σ charges on tagged entries) can be
    compared to an optional budget. Distinct from réglementaire ``fonds dédiés``
    (19x): this is a *piloting* layer. One entry belongs to at most one event.
    """

    __tablename__ = "evenement"
    __table_args__ = (
        UniqueConstraint("association_id", "nom", name="uq_evenement_assoc_nom"),
    )

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    association_id: str = Field(foreign_key="association.id", index=True)
    nom: str
    description: str | None = None
    date_debut: date | None = None
    date_fin: date | None = None
    budget_recettes: Decimal | None = Field(
        default=None, max_digits=12, decimal_places=2
    )
    budget_depenses: Decimal | None = Field(
        default=None, max_digits=12, decimal_places=2
    )
    statut: EvenementStatut = Field(default=EvenementStatut.ACTIF)
    couleur: str | None = None  # UI accent, e.g. "#7C3AED"
    created_at: datetime = Field(default_factory=_utcnow)


class EvenementRead(SQLModel):
    id: str
    nom: str
    description: str | None
    date_debut: date | None
    date_fin: date | None
    budget_recettes: Decimal | None
    budget_depenses: Decimal | None
    statut: EvenementStatut
    couleur: str | None
    # Computed from tagged entries (never stored): produits (cl.7) / charges (cl.6).
    realise_recettes: Decimal
    realise_depenses: Decimal
    resultat: Decimal  # realise_recettes − realise_depenses


# ------------------------------------------------------------------------------
# Dashboard synthesis (T6) — read-only DTOs (no table), period analytics + alerts
# ------------------------------------------------------------------------------


class SyntheseResultat(SQLModel):
    """Result over the period: produits (cl.7) − charges (cl.6)."""

    recettes: Decimal
    depenses: Decimal
    resultat: Decimal


class RepartitionCategorieItem(SQLModel):
    """One slice of the per-category breakdown over the period."""

    categorie_id: str
    libelle: str
    sens: SensCategorie
    montant: Decimal


class RepartitionEvenementItem(SQLModel):
    """One slice of the per-event breakdown over the period."""

    evenement_id: str
    nom: str
    couleur: str | None
    recettes: Decimal
    depenses: Decimal
    resultat: Decimal


class CourbePoint(SQLModel):
    """One point of the treasury balance curve (cumulative end-of-day balance)."""

    date: date
    solde: Decimal


class AlerteEvenement(SQLModel):
    evenement_id: str
    nom: str
    budget_depenses: Decimal
    realise_depenses: Decimal


class AlerteExercice(SQLModel):
    exercice_id: str
    libelle: str
    date_fin: date


class SyntheseAlertes(SQLModel):
    """Current actionable alerts (independent of the selected period)."""

    brouillons: int  # entries still in draft, to validate
    evenements_depasses: list[AlerteEvenement]
    exercices_a_cloturer: list[AlerteExercice]


class SyntheseRead(SQLModel):
    """Consolidated dashboard: period analytics + current alerts, in one read."""

    date_from: date
    date_to: date
    resultat: SyntheseResultat
    repartition_categories: list[RepartitionCategorieItem]
    repartition_evenements: list[RepartitionEvenementItem]
    courbe_tresorerie: list[CourbePoint]
    alertes: SyntheseAlertes


class Justificatif(SQLModel, table=True):
    """A supporting document (invoice, receipt…) attached to an entry (§15.7).

    Metadata lives here; the bytes live behind a ``FileStorage`` (local volume
    today, S3/MinIO later) addressed by the server-generated ``storage_key``.
    The stored ``content_type`` is the one sniffed from the file, not the one
    the client declared.
    """

    __tablename__ = "justificatif"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    association_id: str = Field(foreign_key="association.id", index=True)
    ecriture_id: str | None = Field(default=None, foreign_key="ecriture.id", index=True)
    filename: str  # sanitized original name, for display/download only
    content_type: str  # canonical, sniffed from the bytes
    size: int
    storage_key: str = Field(unique=True, index=True)
    uploaded_by: str | None = Field(default=None, foreign_key="user.id")
    created_at: datetime = Field(default_factory=_utcnow)


class JustificatifRead(SQLModel):
    id: str
    ecriture_id: str | None
    filename: str
    content_type: str
    size: int
    created_at: datetime


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


class CategorieSaisieRead(SQLModel):
    id: str
    sens: SensCategorie
    libelle: str
    compte_id: str
    journal_id: str
    is_active: bool
    ordre: int


class LigneEcritureRead(SQLModel):
    id: str
    compte_id: str
    libelle: str
    debit: Decimal
    credit: Decimal


class EcritureRead(SQLModel):
    id: str
    exercice_id: str
    journal_id: str
    categorie_id: str | None
    date: date
    numero_piece: int
    libelle: str
    tiers_id: str | None
    evenement_id: str | None
    reference_externe: str | None
    mode_reglement: ModeReglement | None
    statut: EcritureStatut
    origine: EcritureOrigine
    extourne_de_id: str | None
    created_at: datetime
    validated_at: datetime | None


class EcritureDetailRead(EcritureRead):
    lignes: list[LigneEcritureRead] = []


class EcritureListItem(EcritureRead):
    """A journal row: the entry plus its total amount and human journal code,
    so the listing needs no per-row follow-up request."""

    montant: Decimal  # total débit = total crédit (entries are balanced)
    journal_code: str


class BalanceCompteRead(SQLModel):
    """One row of the trial balance (balance des comptes)."""

    compte_id: str
    numero: str
    libelle: str
    total_debit: Decimal
    total_credit: Decimal
    solde: Decimal  # débit - crédit (positif = solde débiteur)


class GrandLivreLigneRead(SQLModel):
    """One movement of an account's ledger (grand livre), with running balance."""

    ecriture_id: str
    date: date
    numero_piece: int
    journal_id: str
    libelle: str
    debit: Decimal
    credit: Decimal
    solde: Decimal  # cumul débit - crédit jusqu'à cette ligne
