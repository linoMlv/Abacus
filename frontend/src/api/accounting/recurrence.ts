/** Recurring entries (§5 Récurrences), mirrors the backend. */

import type { ModeReglement } from './common';

export type Periodicite = 'hebdomadaire' | 'mensuelle' | 'trimestrielle' | 'annuelle';

export const PERIODICITE_LABELS: Record<Periodicite, string> = {
  hebdomadaire: 'Hebdomadaire',
  mensuelle: 'Mensuelle',
  trimestrielle: 'Trimestrielle',
  annuelle: 'Annuelle',
};

export type RecurrenceMode = 'proposition' | 'auto';

export const RECURRENCE_MODE_LABELS: Record<RecurrenceMode, string> = {
  proposition: 'Proposition à valider',
  auto: 'Automatique',
};

export interface Recurrence {
  id: string;
  libelle: string;
  categorie_id: string;
  compte_tresorerie_id: string;
  montant: string;
  tiers_id: string | null;
  evenement_id: string | null;
  reference_externe: string | null;
  mode_reglement: ModeReglement | null;
  periodicite: Periodicite;
  prochaine_echeance: string;
  date_fin: string | null;
  mode: RecurrenceMode;
  actif: boolean;
}

export interface CreateRecurrenceInput {
  libelle: string;
  categorie_id: string;
  compte_tresorerie_id: string;
  montant: string;
  periodicite: Periodicite;
  prochaine_echeance: string;
  mode: RecurrenceMode;
  date_fin?: string;
}

export interface UpdateRecurrenceInput {
  libelle?: string;
  categorie_id?: string;
  compte_tresorerie_id?: string;
  montant?: string;
  periodicite?: Periodicite;
  prochaine_echeance?: string;
  date_fin?: string | null;
  mode?: RecurrenceMode;
  actif?: boolean;
}

export interface GenerationResult {
  generees: number;
}
