import type { Sens } from './accounting/common';
import { api, apiUrl, assoBase as base, qs } from './client';

/** One budget row: prévu (editable), réalisé (from the ledger) and écart. */
export interface LigneBudget {
  categorie_id: string;
  libelle: string;
  sens: Sens;
  montant_prevu: string;
  realise: string;
  ecart: string;
}

/** The budget of one exercice: every active category, with totals and results. */
export interface Budget {
  exercice_id: string;
  exercice_libelle: string;
  exercice_statut: 'ouvert' | 'cloture';
  lignes: LigneBudget[];
  total_recettes_prevu: string;
  total_recettes_realise: string;
  total_depenses_prevu: string;
  total_depenses_realise: string;
  resultat_prevu: string;
  resultat_realise: string;
}

export interface BudgetUpsertInput {
  exercice_id: string;
  lignes: { categorie_id: string; montant_prevu: string }[];
}

export const budgetApi = {
  getBudget: (associationId: string, exerciceId?: string) =>
    api.get<Budget>(`${base(associationId)}/budget${qs({ exercice_id: exerciceId })}`),
  saveBudget: (associationId: string, input: BudgetUpsertInput) =>
    api.put<Budget>(`${base(associationId)}/budget`, input),
  budgetPdfUrl: (associationId: string, exerciceId?: string) =>
    apiUrl(`${base(associationId)}/exports/budget.pdf${qs({ exercice_id: exerciceId })}`),
  budgetXlsxUrl: (associationId: string, exerciceId?: string) =>
    apiUrl(`${base(associationId)}/exports/budget.xlsx${qs({ exercice_id: exerciceId })}`),
};
