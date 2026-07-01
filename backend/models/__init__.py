"""Domain models, split by bounded context.

Historically a single ``models.py`` module. Kept importable exactly as before
(``from models import X``) via this package's re-exports, so no call site had to
change when the file was split.
"""

from .association import (
    Association,
    AuditLog,
    AuditLogRead,
    LogEntry,
    LogEntryRead,
    RefreshSession,
)
from .categorie import CategorieSaisie, CategorieSaisieRead, SensCategorie
from .common import utcnow
from .ecriture import (
    BalanceCompteRead,
    Ecriture,
    EcritureDetailRead,
    EcritureListItem,
    EcritureOrigine,
    EcritureRead,
    EcritureStatut,
    GrandLivreLigneRead,
    LigneEcriture,
    LigneEcritureRead,
    ModeReglement,
)
from .evenement import Evenement, EvenementRead, EvenementStatut
from .identity import (
    Invitation,
    Membership,
    MembershipRead,
    MembershipStatus,
    PermissionPreset,
    Role,
    User,
)
from .justificatif import Justificatif, JustificatifRead
from .referentiel import (
    AffectationResultat,
    ClotureResult,
    Compte,
    CompteRead,
    CompteTresorerieRead,
    CompteType,
    Exercice,
    ExerciceCreate,
    ExerciceRead,
    ExerciceStatut,
    Journal,
    JournalRead,
    TypeTresorerie,
)
from .synthese import (
    AlerteEvenement,
    AlerteExercice,
    CourbePoint,
    RepartitionCategorieItem,
    RepartitionEvenementItem,
    SyntheseAlertes,
    SyntheseRead,
    SyntheseResultat,
)
from .tiers import Tiers, TiersRead, TypeTiers

__all__ = [
    "AffectationResultat",
    "AlerteEvenement",
    "AlerteExercice",
    "Association",
    "AuditLog",
    "AuditLogRead",
    "BalanceCompteRead",
    "CategorieSaisie",
    "CategorieSaisieRead",
    "ClotureResult",
    "Compte",
    "CompteRead",
    "CompteTresorerieRead",
    "CompteType",
    "CourbePoint",
    "Ecriture",
    "EcritureDetailRead",
    "EcritureListItem",
    "EcritureOrigine",
    "EcritureRead",
    "EcritureStatut",
    "Evenement",
    "EvenementRead",
    "EvenementStatut",
    "Exercice",
    "ExerciceCreate",
    "ExerciceRead",
    "ExerciceStatut",
    "GrandLivreLigneRead",
    "Invitation",
    "Journal",
    "JournalRead",
    "Justificatif",
    "JustificatifRead",
    "LigneEcriture",
    "LigneEcritureRead",
    "LogEntry",
    "LogEntryRead",
    "Membership",
    "MembershipRead",
    "MembershipStatus",
    "ModeReglement",
    "PermissionPreset",
    "RefreshSession",
    "RepartitionCategorieItem",
    "RepartitionEvenementItem",
    "Role",
    "SensCategorie",
    "SyntheseAlertes",
    "SyntheseRead",
    "SyntheseResultat",
    "Tiers",
    "TiersRead",
    "TypeTiers",
    "TypeTresorerie",
    "User",
    "utcnow",
]
