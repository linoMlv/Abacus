/** Lifecycle of an event, mirrors the backend `EvenementStatut`. */
export type EvenementStatut = 'actif' | 'cloture';

export const EVENEMENT_STATUT_LABELS: Record<EvenementStatut, string> = {
  actif: 'Actif',
  cloture: 'Clôturé',
};

/** An analytic event with its budget and computed réalisé (decimal strings). */
export interface Evenement {
  id: string;
  nom: string;
  description: string | null;
  date_debut: string | null;
  date_fin: string | null;
  budget_recettes: string | null;
  budget_depenses: string | null;
  statut: EvenementStatut;
  couleur: string | null;
  realise_recettes: string;
  realise_depenses: string;
  resultat: string;
}

export interface CreateEvenementInput {
  nom: string;
  description?: string;
  date_debut?: string;
  date_fin?: string;
  budget_recettes?: string;
  budget_depenses?: string;
  couleur?: string;
}

export interface UpdateEvenementInput extends Partial<CreateEvenementInput> {
  statut?: EvenementStatut;
}
