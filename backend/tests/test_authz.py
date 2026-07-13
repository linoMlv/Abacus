"""RBAC permission-matrix tests.

These guard the security contract of ``authz.py``: every role is defined, the
hierarchy is monotonic, ADMIN is a complete superset, and read-only roles never
gain a write capability by accident.
"""

from authz import (
    PERMISSION_CATALOG,
    ROLE_PERMISSIONS,
    Permission,
    effective_permissions,
    has_permission,
    permissions_for,
)
from models import Role

# Permissions that must never be granted to a read-only (VIEWER) role.
_WRITE_PERMISSIONS = {
    Permission.ENTRY_CREATE_SIMPLE,
    Permission.ENTRY_CREATE_MANUAL,
    Permission.ENTRY_VALIDATE,
    Permission.ENTRY_DELETE,
    Permission.EXERCISE_CLOSE,
    Permission.BANK_RECONCILE,
    Permission.TIERS_MANAGE,
    Permission.DONATION_MANAGE,
    Permission.BUDGET_MANAGE,
    Permission.MEMBER_MANAGE,
    Permission.SETTINGS_MANAGE,
    Permission.APIKEY_MANAGE,
}


def test_every_role_is_defined():
    assert set(ROLE_PERMISSIONS) == set(Role)


def test_admin_holds_every_permission():
    # ADMIN must be a complete superset so a newly added permission is granted
    # to admins automatically and cannot be silently forgotten.
    assert permissions_for(Role.ADMIN) == frozenset(Permission)


def test_hierarchy_is_monotonic():
    viewer = permissions_for(Role.VIEWER)
    treasurer = permissions_for(Role.TREASURER)
    accountant = permissions_for(Role.ACCOUNTANT)
    admin = permissions_for(Role.ADMIN)

    assert viewer < treasurer
    assert treasurer < accountant
    assert accountant <= admin
    assert accountant < admin  # admin strictly larger (admin-only perms)


def test_viewer_is_read_only():
    viewer = permissions_for(Role.VIEWER)
    assert viewer == {Permission.DASHBOARD_VIEW, Permission.REPORT_VIEW}
    assert viewer.isdisjoint(_WRITE_PERMISSIONS)


def test_treasurer_can_do_simple_entry_but_not_accounting_authority():
    role = Role.TREASURER
    assert has_permission(role, Permission.ENTRY_CREATE_SIMPLE)
    assert has_permission(role, Permission.BANK_RECONCILE)
    assert has_permission(role, Permission.DONATION_MANAGE)
    # No accounting authority and no administration.
    for perm in (
        Permission.ENTRY_CREATE_MANUAL,
        Permission.ENTRY_VALIDATE,
        Permission.EXERCISE_CLOSE,
        Permission.REPORT_EXPORT_FEC,
        Permission.MEMBER_MANAGE,
        Permission.SETTINGS_MANAGE,
        Permission.APIKEY_MANAGE,
        Permission.LOGS_VIEW,
    ):
        assert not has_permission(role, perm), perm


def test_accountant_has_accounting_authority_but_not_administration():
    role = Role.ACCOUNTANT
    for perm in (
        Permission.ENTRY_CREATE_MANUAL,
        Permission.ENTRY_VALIDATE,
        Permission.EXERCISE_CLOSE,
        Permission.REPORT_EXPORT_FEC,
    ):
        assert has_permission(role, perm), perm
    # Administration stays with admin only.
    for perm in (
        Permission.MEMBER_MANAGE,
        Permission.SETTINGS_MANAGE,
        Permission.APIKEY_MANAGE,
        Permission.LOGS_VIEW,
    ):
        assert not has_permission(role, perm), perm


def test_account_manage_is_accounting_authority_not_treasurer():
    """Editing the chart of accounts is durable and structural: expert-comptable
    (and admin), never the day-to-day treasurer, who works with categories."""
    assert has_permission(Role.ACCOUNTANT, Permission.ACCOUNT_MANAGE)
    assert has_permission(Role.ADMIN, Permission.ACCOUNT_MANAGE)
    assert not has_permission(Role.TREASURER, Permission.ACCOUNT_MANAGE)
    assert not has_permission(Role.VIEWER, Permission.ACCOUNT_MANAGE)


def test_logs_view_is_admin_only():
    for role in Role:
        expected = role is Role.ADMIN
        assert has_permission(role, Permission.LOGS_VIEW) is expected


def test_has_permission_matches_permissions_for():
    for role in Role:
        granted = permissions_for(role)
        for perm in Permission:
            assert has_permission(role, perm) is (perm in granted)


def test_permission_values_are_unique_namespaced_strings():
    values = [p.value for p in Permission]
    assert len(values) == len(set(values))
    assert all(":" in v for v in values)


def test_role_values_are_stable():
    # These strings are persisted / audited — pin them.
    assert {r.value for r in Role} == {
        "admin",
        "accountant",
        "treasurer",
        "viewer",
    }


# --------------------------------------------------------------------------- #
# Effective permissions (T8): per-member overrides + custom preset base.
# --------------------------------------------------------------------------- #
def test_effective_without_override_equals_role():
    for role in Role:
        assert effective_permissions(role) == permissions_for(role)
        assert effective_permissions(role, None, {}) == permissions_for(role)


def test_admin_is_immune_to_overrides():
    # An admin always holds every permission; a revoke override cannot strip it,
    # so an association can never be locked out of administration.
    overrides = {p.value: False for p in Permission}
    assert effective_permissions(Role.ADMIN, None, overrides) == frozenset(Permission)
    # Even with a restrictive custom preset, an admin stays a full superset.
    assert effective_permissions(
        Role.ADMIN, frozenset({Permission.DASHBOARD_VIEW}), overrides
    ) == frozenset(Permission)


def test_grant_override_adds_a_permission_above_the_role():
    # A viewer granted TIERS_MANAGE gains exactly that, nothing else.
    eff = effective_permissions(
        Role.VIEWER, None, {Permission.TIERS_MANAGE.value: True}
    )
    assert Permission.TIERS_MANAGE in eff
    assert eff == permissions_for(Role.VIEWER) | {Permission.TIERS_MANAGE}


def test_revoke_override_removes_a_permission_from_the_role():
    # A treasurer can have a single capability revoked.
    eff = effective_permissions(
        Role.TREASURER, None, {Permission.DONATION_MANAGE.value: False}
    )
    assert Permission.DONATION_MANAGE not in eff
    assert eff == permissions_for(Role.TREASURER) - {Permission.DONATION_MANAGE}


def test_custom_preset_replaces_the_role_base():
    # With a preset assigned, the base is the preset's set (not the role's),
    # then overrides apply on top.
    preset = frozenset({Permission.DASHBOARD_VIEW, Permission.REPORT_VIEW})
    eff = effective_permissions(
        Role.VIEWER, preset, {Permission.BUDGET_MANAGE.value: True}
    )
    assert eff == preset | {Permission.BUDGET_MANAGE}


def test_unknown_override_keys_are_ignored():
    # Defensive: a stale/forged key in the stored overrides changes nothing.
    eff = effective_permissions(
        Role.TREASURER, None, {"not:a:permission": True, "also-bogus": False}
    )
    assert eff == permissions_for(Role.TREASURER)


def test_permission_catalog_covers_every_permission_once():
    catalog_perms = [info.permission for info in PERMISSION_CATALOG]
    assert set(catalog_perms) == set(Permission)
    assert len(catalog_perms) == len(Permission)  # no duplicates
    # Every entry carries a human group + label for the admin UI.
    for info in PERMISSION_CATALOG:
        assert info.group and info.label
