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
