import type { EcritureStatut } from '@/api/accounting';

export const STATUT_LABELS: Record<EcritureStatut, string> = {
  brouillon: 'Brouillon',
  validee: 'Validée',
};

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
