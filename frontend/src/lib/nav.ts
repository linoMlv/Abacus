import {
  BookOpen,
  Building2,
  CalendarRange,
  HeartHandshake,
  LayoutDashboard,
  ListTree,
  type LucideIcon,
  PencilLine,
  PiggyBank,
  Repeat,
  Settings,
  FileBarChart,
  Users,
} from 'lucide-react';

import { PERMISSIONS, type Permission } from '@/lib/permissions';

export interface NavItem {
  /** Path segment under /asso/:associationId */
  segment: string;
  label: string;
  icon: LucideIcon;
  /** Permission required to access the page; the sidebar greys it out otherwise. */
  permission: Permission;
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
        permission: PERMISSIONS.DASHBOARD_VIEW,
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
        permission: PERMISSIONS.ENTRY_CREATE_SIMPLE,
      },
      { segment: 'journal', label: 'Journal', icon: BookOpen, permission: PERMISSIONS.REPORT_VIEW },
      {
        segment: 'evenements',
        label: 'Événements',
        icon: CalendarRange,
        permission: PERMISSIONS.REPORT_VIEW,
      },
      { segment: 'comptes', label: 'Comptes', icon: ListTree, permission: PERMISSIONS.REPORT_VIEW },
      { segment: 'tiers', label: 'Tiers', icon: Users, permission: PERMISSIONS.TIERS_MANAGE },
      {
        segment: 'banque',
        label: 'Banque',
        icon: Building2,
        permission: PERMISSIONS.BANK_RECONCILE,
      },
      {
        segment: 'recurrences',
        label: 'Récurrences',
        icon: Repeat,
        permission: PERMISSIONS.ENTRY_CREATE_SIMPLE,
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
        permission: PERMISSIONS.BUDGET_MANAGE,
      },
      {
        segment: 'rapports',
        label: 'Rapports',
        icon: FileBarChart,
        permission: PERMISSIONS.REPORT_VIEW,
      },
      {
        segment: 'dons',
        label: 'Dons',
        icon: HeartHandshake,
        permission: PERMISSIONS.DONATION_MANAGE,
      },
    ],
  },
];

/** Pinned to the bottom of the sidebar. */
export const SETTINGS_ITEM: NavItem = {
  segment: 'parametres',
  label: 'Paramètres',
  icon: Settings,
  permission: PERMISSIONS.MEMBER_MANAGE,
};

/** Every navigable segment, for route generation and lookups. */
export const ALL_NAV_ITEMS: NavItem[] = [...NAV_SECTIONS.flatMap((s) => s.items), SETTINGS_ITEM];
