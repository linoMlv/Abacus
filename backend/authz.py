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

from dataclasses import dataclass
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
    EVENT_MANAGE = "event:manage"  # événements (axe analytique : CRUD, quick-add)
    BANK_RECONCILE = "bank:reconcile"
    RECURRENCE_MANAGE = "recurrence:manage"  # écritures récurrentes (CRUD, génération)
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
    Permission.EVENT_MANAGE,
    Permission.BANK_RECONCILE,
    Permission.RECURRENCE_MANAGE,
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
    """True iff ``role`` grants ``permission`` (role preset only, no overrides)."""
    return permission in ROLE_PERMISSIONS[role]


def effective_permissions(
    role: Role,
    preset_permissions: frozenset[Permission] | None = None,
    overrides: dict[str, bool] | None = None,
) -> frozenset[Permission]:
    """Server-authoritative effective permissions of a membership (T8).

    Layered, in precedence order:

    1. **ADMIN is immune** — an admin always holds *every* permission (the
       superset invariant). Neither a custom preset nor a revoke override can
       strip an admin, which is what guarantees an association can never be
       locked out of its own administration via a per-member override.
    2. **Base** — a custom :class:`~models.PermissionPreset` (``preset_permissions``)
       *replaces* the role's set when one is assigned; otherwise the built-in
       role's set applies.
    3. **Overrides** — the per-member ``{permission_value: bool}`` map then
       grants (``True``) or revokes (``False``) individual permissions on top.
       Unknown/stale keys are ignored (defense against forged stored state).
    """
    if role is Role.ADMIN:
        return _ALL
    base = (
        preset_permissions if preset_permissions is not None else ROLE_PERMISSIONS[role]
    )
    if not overrides:
        return base
    granted = {p for p in Permission if overrides.get(p.value) is True}
    revoked = {p for p in Permission if overrides.get(p.value) is False}
    return frozenset((base | granted) - revoked)


@dataclass(frozen=True)
class PermissionInfo:
    """One catalog entry: a permission with a human group + label for the UI."""

    permission: Permission
    group: str
    label: str


# Human catalog of every permission, grouped for the admin permissions panel.
# Order is presentation order; it must cover ``Permission`` exhaustively (tested).
PERMISSION_CATALOG: tuple[PermissionInfo, ...] = (
    # Consultation
    PermissionInfo(Permission.DASHBOARD_VIEW, "Consultation", "Voir la synthèse"),
    PermissionInfo(
        Permission.REPORT_VIEW, "Consultation", "Voir les états et le grand livre"
    ),
    # Saisie & écritures comptables
    PermissionInfo(
        Permission.ENTRY_CREATE_SIMPLE, "Saisie", "Saisir recette / dépense"
    ),
    PermissionInfo(
        Permission.ENTRY_CREATE_TRANSFER, "Saisie", "Saisir un virement interne"
    ),
    PermissionInfo(
        Permission.ENTRY_CREATE_MANUAL, "Saisie", "Saisir une écriture manuelle"
    ),
    PermissionInfo(Permission.ENTRY_VALIDATE, "Saisie", "Valider une écriture"),
    PermissionInfo(Permission.ENTRY_DELETE, "Saisie", "Supprimer un brouillon"),
    # Clôture & exports légaux
    PermissionInfo(Permission.EXERCISE_CLOSE, "Clôture", "Clôturer un exercice"),
    PermissionInfo(Permission.REPORT_EXPORT_FEC, "Clôture", "Exporter le FEC"),
    # Périphérie métier
    PermissionInfo(
        Permission.TRESORERIE_MANAGE, "Gestion", "Gérer les comptes de trésorerie"
    ),
    PermissionInfo(Permission.CATEGORIE_MANAGE, "Gestion", "Gérer les catégories"),
    PermissionInfo(Permission.ATTACHMENT_MANAGE, "Gestion", "Gérer les justificatifs"),
    PermissionInfo(Permission.EVENT_MANAGE, "Gestion", "Gérer les événements"),
    PermissionInfo(
        Permission.BANK_RECONCILE, "Gestion", "Rapprocher les relevés bancaires"
    ),
    PermissionInfo(
        Permission.RECURRENCE_MANAGE, "Gestion", "Gérer les écritures récurrentes"
    ),
    PermissionInfo(Permission.TIERS_MANAGE, "Gestion", "Gérer les tiers"),
    PermissionInfo(
        Permission.DONATION_MANAGE, "Gestion", "Gérer les dons et reçus fiscaux"
    ),
    PermissionInfo(Permission.BUDGET_MANAGE, "Gestion", "Gérer le budget"),
    # Administration de l'association
    PermissionInfo(
        Permission.MEMBER_MANAGE, "Administration", "Gérer les membres et invitations"
    ),
    PermissionInfo(
        Permission.SETTINGS_MANAGE, "Administration", "Gérer les paramètres"
    ),
    PermissionInfo(Permission.APIKEY_MANAGE, "Administration", "Gérer les clés API"),
    PermissionInfo(Permission.LOGS_VIEW, "Administration", "Consulter les journaux"),
)
