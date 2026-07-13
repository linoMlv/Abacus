import type { EcritureListItem, EcritureOrigine, EcritureStatut } from '@/api/accounting';

export const STATUT_LABELS: Record<EcritureStatut, string> = {
  brouillon: 'Brouillon',
  validee: 'Validée',
};

/** Why an entry exists — surfaced in the accounting view. */
export const ORIGINE_LABELS: Record<EcritureOrigine, string> = {
  saisie_simple: 'Saisie',
  virement: 'Virement',
  manuelle: 'Manuelle',
  import: 'Import bancaire',
  recurrence: 'Récurrence',
  a_nouveau: 'À-nouveau',
  extourne: 'Contre-passation',
  cloture: 'Clôture',
};

/** Shared shape of the two journal tables (plain-language and accounting). */
export interface JournalTableProps {
  associationId: string;
  rows: EcritureListItem[];
  onSelect: (id: string) => void;
  selectable: boolean;
  selectedIds: string[];
  onToggleRow: (id: string) => void;
  onToggleAll: () => void;
}

export interface FilterOption {
  value: string;
  label: string;
}

export interface Facet {
  key: string;
  title: string;
  options: FilterOption[];
  selected: string[];
  onToggle: (value: string) => void;
  /** Cap the list height with an inner scroll (for potentially long lists). */
  scroll?: boolean;
}
