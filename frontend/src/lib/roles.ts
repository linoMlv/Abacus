import type { Role } from '@/api/auth';

export const ROLE_LABELS: Record<Role, string> = {
  admin: 'Administrateur',
  accountant: 'Expert-comptable',
  treasurer: 'Trésorier',
  viewer: 'Lecteur',
};

/**
 * Mirror of the backend `ENTRY_CREATE_SIMPLE` grant: every role except the
 * read-only viewer may record assisted recette/dépense entries. This only
 * drives the UI — the server independently enforces the permission on every
 * request, so a forged role grants nothing.
 */
export function canCreateSimpleEntry(role: Role): boolean {
  return role !== 'viewer';
}

/** Mirror of `ENTRY_VALIDATE`: only the accountant and admin lock entries. */
export function canValidateEntry(role: Role): boolean {
  return role === 'accountant' || role === 'admin';
}

/** Mirror of `ENTRY_DELETE`: every role except the read-only viewer. */
export function canDeleteEntry(role: Role): boolean {
  return role !== 'viewer';
}

/** Mirror of `TRESORERIE_MANAGE`: treasurer and up manage treasury accounts. */
export function canManageTresorerie(role: Role): boolean {
  return role !== 'viewer';
}

/** Mirror of `CATEGORIE_MANAGE`: treasurer and up manage entry categories. */
export function canManageCategorie(role: Role): boolean {
  return role !== 'viewer';
}

/** Mirror of `TIERS_MANAGE`: treasurer and up manage third parties. */
export function canManageTiers(role: Role): boolean {
  return role !== 'viewer';
}

/** Mirror of `ATTACHMENT_MANAGE`: treasurer and up upload/remove justificatifs. */
export function canManageAttachment(role: Role): boolean {
  return role !== 'viewer';
}
