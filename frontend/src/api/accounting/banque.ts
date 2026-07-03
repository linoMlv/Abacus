/** Bank statement import & reconciliation (§5 Banque), mirrors the backend. */

export type LigneBancaireStatut = 'non_rapproche' | 'rapproche' | 'ignore';

export const LIGNE_BANCAIRE_STATUT_LABELS: Record<LigneBancaireStatut, string> = {
  non_rapproche: 'À rapprocher',
  rapproche: 'Rapprochée',
  ignore: 'Ignorée',
};

/** One CSV import batch, bound to a treasury account. */
export interface ImportReleve {
  id: string;
  compte_id: string;
  filename: string;
  nb_lignes: number;
  created_at: string;
}

/** A single statement movement; `montant` is a signed decimal string. */
export interface LigneBancaire {
  id: string;
  import_id: string;
  compte_id: string;
  date_operation: string;
  libelle: string;
  montant: string;
  statut: LigneBancaireStatut;
  ecriture_id: string | null;
}

/** An existing entry proposed as a match for a statement line (same amount). */
export interface RapprochementSuggestion {
  ecriture_id: string;
  numero_piece: number;
  date: string;
  libelle: string;
  montant: string;
}

/** CSV column mapping sent alongside the uploaded file. */
export interface ImportReleveMapping {
  date_col: number;
  libelle_col: number;
  montant_col?: number;
  debit_col?: number;
  credit_col?: number;
  date_format: string;
  decimal_sep: string;
  delimiter: string;
  has_header: boolean;
}

/** Analytic metadata for creating an entry from a statement line. */
export interface CreerEcritureDepuisLigneInput {
  categorie_id: string;
  evenement_id?: string;
  tiers_id?: string;
  reference_externe?: string;
}
