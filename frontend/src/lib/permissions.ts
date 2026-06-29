/**
 * Fine-grained permission values, mirrored from the backend `Permission` enum
 * (`backend/authz.py`). These are the stable `domain:action` strings the server
 * returns in the association context's effective `permissions` list.
 *
 * The UI gates on the *effective* set (see `usePermissions`), never on the role —
 * so a per-member override takes effect immediately. This is convenience only;
 * the server independently enforces every permission on each request.
 */
export const PERMISSIONS = {
  DASHBOARD_VIEW: 'dashboard:view',
  REPORT_VIEW: 'report:view',
  ENTRY_CREATE_SIMPLE: 'entry:create_simple',
  ENTRY_CREATE_TRANSFER: 'entry:create_transfer',
  ENTRY_CREATE_MANUAL: 'entry:create_manual',
  ENTRY_VALIDATE: 'entry:validate',
  ENTRY_DELETE: 'entry:delete',
  EXERCISE_CLOSE: 'exercise:close',
  REPORT_EXPORT_FEC: 'report:export_fec',
  TRESORERIE_MANAGE: 'tresorerie:manage',
  CATEGORIE_MANAGE: 'categorie:manage',
  ATTACHMENT_MANAGE: 'attachment:manage',
  EVENT_MANAGE: 'event:manage',
  BANK_RECONCILE: 'bank:reconcile',
  TIERS_MANAGE: 'tiers:manage',
  DONATION_MANAGE: 'donation:manage',
  BUDGET_MANAGE: 'budget:manage',
  MEMBER_MANAGE: 'member:manage',
  SETTINGS_MANAGE: 'settings:manage',
  APIKEY_MANAGE: 'apikey:manage',
  LOGS_VIEW: 'logs:view',
} as const;

export type Permission = (typeof PERMISSIONS)[keyof typeof PERMISSIONS];
