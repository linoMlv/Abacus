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
  Users,
} from 'lucide-react';

export interface NavItem {
  /** Path segment under /asso/:associationId */
  segment: string;
  label: string;
  icon: LucideIcon;
}

export interface NavSection {
  label?: string;
  items: NavItem[];
}

/** Primary navigation, grouped for a calmer sidebar. */
export const NAV_SECTIONS: NavSection[] = [
  {
    items: [{ segment: 'synthese', label: 'Synthèse', icon: LayoutDashboard }],
  },
  {
    label: 'Comptabilité',
    items: [
      { segment: 'saisie', label: 'Saisie', icon: PencilLine },
      { segment: 'journal', label: 'Journal', icon: BookOpen },
      { segment: 'comptes', label: 'Comptes', icon: ListTree },
      { segment: 'tiers', label: 'Tiers', icon: Users },
      { segment: 'banque', label: 'Banque', icon: Building2 },
      { segment: 'recurrences', label: 'Récurrences', icon: Repeat },
    ],
  },
  {
    label: 'Pilotage',
    items: [
      { segment: 'budget', label: 'Budget', icon: PiggyBank },
      { segment: 'rapports', label: 'Rapports', icon: FileBarChart },
      { segment: 'dons', label: 'Dons', icon: HeartHandshake },
    ],
  },
];

/** Pinned to the bottom of the sidebar. */
export const SETTINGS_ITEM: NavItem = {
  segment: 'parametres',
  label: 'Paramètres',
  icon: Settings,
};

/** Every navigable segment, for route generation and lookups. */
export const ALL_NAV_ITEMS: NavItem[] = [...NAV_SECTIONS.flatMap((s) => s.items), SETTINGS_ITEM];
