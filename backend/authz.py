"""Role-based access control (RBAC) for V3 multi-association access.

Single source of truth mapping a :class:`~models.Role` (held per association
via a ``Membership``) to the set of fine-grained permissions it grants.

Design rules (security-critical — keep them true):

* **Server-authoritative**: routes must check ``has_permission`` server-side;
  the UI hiding a button is never an authorization.
* **ADMIN is a superset**: an association admin holds *every* permission within
  *their* association. This is deliberate — a small association's founder must
  be able to do everything in their own tenant. Least privilege is preserved
  *across* tenants (you only hold roles where you were granted them) and via the
  lesser roles for other members. Because ADMIN is computed as ``set(Permission)``
  a newly added permission is automatically granted to admins and must be
  *explicitly* added to any lesser role — there is no silent over-grant.
* **Monotonic hierarchy**: VIEWER ⊂ TREASURER ⊂ ACCOUNTANT ⊂ ADMIN.
"""

from enum import Enum

from models import Role


class Permission(str, Enum):
    """Fine-grained capability, independent of role.

    Values are stable strings (``domain:action``) — they may be logged/audited.
    """

    # Consultation
    DASHBOARD_VIEW = "dashboard:view"
    REPORT_VIEW = "report:view"  # bilan, compte de résultat, grand livre, balance

    # Saisie & écritures comptables
    ENTRY_CREATE_SIMPLE = "entry:create_simple"  # saisie assistée recette/dépense
    ENTRY_CREATE_TRANSFER = "entry:create_transfer"  # virement interne (trésorerie)
    ENTRY_CREATE_MANUAL = "entry:create_manual"  # écriture manuelle multi-lignes
    ENTRY_VALIDATE = "entry:validate"  # passage brouillon -> validée
    ENTRY_DELETE = "entry:delete"  # suppression d'un brouillon / contre-passation

    # Clôture & exports légaux
    EXERCISE_CLOSE = "exercise:close"
    REPORT_EXPORT_FEC = "report:export_fec"

    # Périphérie métier
    TRESORERIE_MANAGE = "tresorerie:manage"  # comptes de trésorerie (création/édition)
    CATEGORIE_MANAGE = "categorie:manage"  # catégories de saisie (CRUD, quick-add)
    ATTACHMENT_MANAGE = "attachment:manage"  # justificatifs (upload/suppression)
    BANK_RECONCILE = "bank:reconcile"
    TIERS_MANAGE = "tiers:manage"
    DONATION_MANAGE = "donation:manage"  # dons & reçus fiscaux
    BUDGET_MANAGE = "budget:manage"

    # Administration de l'association
    MEMBER_MANAGE = "member:manage"  # invitations, rôles, suspension
    SETTINGS_MANAGE = "settings:manage"  # paramètres, TVA, plan comptable
    APIKEY_MANAGE = "apikey:manage"
    LOGS_VIEW = "logs:view"  # logs de SON association (diagnostic admin)


# Read-only: président / CA.
_VIEWER: frozenset[Permission] = frozenset(
    {
        Permission.DASHBOARD_VIEW,
        Permission.REPORT_VIEW,
    }
)

# Day-to-day operational role: trésorier. Manages treasury accounts (incl.
# on-the-fly quick-add during saisie) so the "douce" UX holds; a finer
# admin-only-for-durable-edit split is deferred to the per-user override panel (T8).
_TREASURER: frozenset[Permission] = _VIEWER | {
    Permission.ENTRY_CREATE_SIMPLE,
    Permission.ENTRY_CREATE_TRANSFER,
    Permission.ENTRY_DELETE,
    Permission.TRESORERIE_MANAGE,
    Permission.CATEGORIE_MANAGE,
    Permission.ATTACHMENT_MANAGE,
    Permission.BANK_RECONCILE,
    Permission.TIERS_MANAGE,
    Permission.DONATION_MANAGE,
    Permission.BUDGET_MANAGE,
}

# Full accounting authority: expert-comptable.
_ACCOUNTANT: frozenset[Permission] = _TREASURER | {
    Permission.ENTRY_CREATE_MANUAL,
    Permission.ENTRY_VALIDATE,
    Permission.EXERCISE_CLOSE,
    Permission.REPORT_EXPORT_FEC,
}

# Admin holds every permission within the association (superset).
_ALL: frozenset[Permission] = frozenset(Permission)


ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.ADMIN: _ALL,
    Role.ACCOUNTANT: _ACCOUNTANT,
    Role.TREASURER: _TREASURER,
    Role.VIEWER: _VIEWER,
}


def permissions_for(role: Role) -> frozenset[Permission]:
    """Return the immutable permission set granted by ``role``."""
    return ROLE_PERMISSIONS[role]


def has_permission(role: Role, permission: Permission) -> bool:
    """True iff ``role`` grants ``permission``."""
    return permission in ROLE_PERMISSIONS[role]
