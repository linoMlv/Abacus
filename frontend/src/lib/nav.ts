import {
  BookOpen,
  Building2,
  HeartHandshake,
  LayoutDashboard,
  ListTree,
  type LucideIcon,
  PencilLine,
  PiggyBank,
  Repeat,
  Settings,
  FileBarChart,
} from 'lucide-react';

import { PERMISSIONS, type Permission } from '@/lib/permissions';

export interface NavItem {
  /** Path segment under /asso/:associationId */
  segment: string;
  label: string;
  icon: LucideIcon;
  /**
   * Permissions that grant access to the page (any one suffices). A page that
   * groups several features (e.g. Saisie: operations + categories + tiers +
   * events) lists all of them, so holding any keeps the page reachable; the page
   * itself then gates each tab/section. The sidebar greys the page out only when
   * the user has none.
   */
  permissions: Permission[];
}

export interface NavSection {
  label?: string;
  items: NavItem[];
}

/** Primary navigation, grouped for a calmer sidebar. */
export const NAV_SECTIONS: NavSection[] = [
  {
    items: [
      {
        segment: 'synthese',
        label: 'Synthèse',
        icon: LayoutDashboard,
        permissions: [PERMISSIONS.DASHBOARD_VIEW],
      },
    ],
  },
  {
    label: 'Comptabilité',
    items: [
      {
        segment: 'saisie',
        label: 'Saisie',
        icon: PencilLine,
        // Hub: operations + the management of categories / tiers / events.
        permissions: [
          PERMISSIONS.ENTRY_CREATE_SIMPLE,
          PERMISSIONS.ENTRY_CREATE_TRANSFER,
          PERMISSIONS.CATEGORIE_MANAGE,
          PERMISSIONS.TIERS_MANAGE,
          PERMISSIONS.EVENT_MANAGE,
        ],
      },
      {
        segment: 'journal',
        label: 'Journal',
        icon: BookOpen,
        permissions: [PERMISSIONS.REPORT_VIEW],
      },
      {
        segment: 'comptes',
        label: 'Comptes',
        icon: ListTree,
        permissions: [PERMISSIONS.REPORT_VIEW],
      },
      {
        segment: 'banque',
        label: 'Banque',
        icon: Building2,
        permissions: [PERMISSIONS.BANK_RECONCILE],
      },
      {
        segment: 'recurrences',
        label: 'Récurrences',
        icon: Repeat,
        permissions: [PERMISSIONS.RECURRENCE_MANAGE],
      },
    ],
  },
  {
    label: 'Pilotage',
    items: [
      {
        segment: 'budget',
        label: 'Budget',
        icon: PiggyBank,
        permissions: [PERMISSIONS.BUDGET_MANAGE],
      },
      {
        segment: 'rapports',
        label: 'Rapports',
        icon: FileBarChart,
        permissions: [PERMISSIONS.REPORT_VIEW],
      },
      {
        segment: 'dons',
        label: 'Dons',
        icon: HeartHandshake,
        permissions: [PERMISSIONS.DONATION_MANAGE],
      },
    ],
  },
];

/** Pinned to the bottom of the sidebar. */
export const SETTINGS_ITEM: NavItem = {
  segment: 'parametres',
  label: 'Paramètres',
  icon: Settings,
  // Members, Exercices and Comptabilité tabs; the page gates each tab itself.
  permissions: [PERMISSIONS.MEMBER_MANAGE, PERMISSIONS.EXERCISE_CLOSE, PERMISSIONS.SETTINGS_MANAGE],
};

/** Every navigable segment, for route generation and lookups. */
export const ALL_NAV_ITEMS: NavItem[] = [...NAV_SECTIONS.flatMap((s) => s.items), SETTINGS_ITEM];
