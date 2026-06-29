import type { Role } from '@/api/auth';

export const ROLE_LABELS: Record<Role, string> = {
  admin: 'Administrateur',
  accountant: 'Expert-comptable',
  treasurer: 'Trésorier',
  viewer: 'Lecteur',
};
