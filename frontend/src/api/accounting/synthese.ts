import type { Sens } from './common';

/** Consolidated dashboard payload (T6). All amounts are decimal strings. */
export interface SyntheseResultat {
  recettes: string;
  depenses: string;
  resultat: string;
}

export interface RepartitionCategorie {
  categorie_id: string;
  libelle: string;
  sens: Sens;
  montant: string;
}

export interface RepartitionEvenement {
  evenement_id: string;
  nom: string;
  couleur: string | null;
  recettes: string;
  depenses: string;
  resultat: string;
}

export interface CourbePoint {
  date: string;
  solde: string;
}

export interface AlerteEvenement {
  evenement_id: string;
  nom: string;
  budget_depenses: string;
  realise_depenses: string;
}

export interface AlerteExercice {
  exercice_id: string;
  libelle: string;
  date_fin: string;
}

export interface SyntheseAlertes {
  brouillons: number;
  evenements_depasses: AlerteEvenement[];
  exercices_a_cloturer: AlerteExercice[];
}

export interface Synthese {
  date_from: string;
  date_to: string;
  resultat: SyntheseResultat;
  repartition_categories: RepartitionCategorie[];
  repartition_evenements: RepartitionEvenement[];
  courbe_tresorerie: CourbePoint[];
  alertes: SyntheseAlertes;
}

/** Period for the synthesis; omit both to let the server use the open exercice. */
export interface SyntheseParams {
  date_from?: string;
  date_to?: string;
}
