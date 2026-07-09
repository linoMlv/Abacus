/** Narrative annexe rubrics (ANC comptes annuels), mirrors the backend. */

export interface AnnexeRubrique {
  id: string;
  exercice_id: string;
  titre: string;
  contenu: string;
  ordre: number;
}

export interface CreateRubriqueInput {
  titre: string;
  contenu?: string;
}

export interface UpdateRubriqueInput {
  titre?: string;
  contenu?: string;
}
