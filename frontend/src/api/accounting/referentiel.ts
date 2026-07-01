import type { CompteType } from './common';

/** One account of the chart of accounts. */
export interface Compte {
  id: string;
  numero: string;
  libelle: string;
  classe: number;
  type: CompteType;
  is_active: boolean;
}

/** One journal (book): BQ, CA, AC, VE, OD… */
export interface Journal {
  id: string;
  code: string;
  libelle: string;
}

/** Lifecycle of a fiscal year, mirrors the backend `ExerciceStatut`. */
export type ExerciceStatut = 'ouvert' | 'cloture';

export const EXERCICE_STATUT_LABELS: Record<ExerciceStatut, string> = {
  ouvert: 'Ouvert',
  cloture: 'Clôturé',
};

/** A fiscal year (exercice). */
export interface Exercice {
  id: string;
  libelle: string;
  date_debut: string;
  date_fin: string;
  statut: ExerciceStatut;
  report_a_nouveau_genere: boolean;
}

export interface CreateExerciceInput {
  libelle: string;
  date_debut: string;
  date_fin: string;
}

/** How the exercice result is affected at closing (report à nouveau vs reserves). */
export interface AffectationResultat {
  report_a_nouveau: string;
  reserves: string;
}

/** Outcome of a closing. */
export interface ClotureResult {
  resultat: string;
  report_a_nouveau: string;
  reserves: string;
  exercice_cloture: Exercice;
  exercice_suivant: Exercice;
}

/** Kind of a named treasury account (where the money is), mirrors the backend. */
export type TypeTresorerie = 'banque' | 'caisse' | 'en_ligne' | 'epargne' | 'autre';

/** A named treasury account with its current balance (decimal string). */
export interface CompteTresorerie {
  id: string;
  numero: string;
  libelle: string;
  type_tresorerie: TypeTresorerie;
  iban: string | null;
  couleur: string | null;
  ordre: number;
  is_active: boolean;
  solde: string;
}

export interface CreateTresorerieInput {
  nom: string;
  type_tresorerie: TypeTresorerie;
  iban?: string;
  couleur?: string;
  solde_initial?: string;
  date_solde_initial?: string;
}

export interface UpdateTresorerieInput {
  nom?: string;
  type_tresorerie?: TypeTresorerie;
  iban?: string;
  couleur?: string;
  ordre?: number;
  is_active?: boolean;
}

/** Human labels for the treasury account types. */
export const TYPE_TRESORERIE_LABELS: Record<TypeTresorerie, string> = {
  banque: 'Banque',
  caisse: 'Caisse',
  en_ligne: 'En ligne',
  epargne: 'Épargne',
  autre: 'Autre',
};
