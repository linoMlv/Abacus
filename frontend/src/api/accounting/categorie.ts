import type { Sens } from './common';

/** A plain-language entry category bridging the simple screen to an account. */
export interface Categorie {
  id: string;
  sens: Sens;
  libelle: string;
  compte_id: string;
  journal_id: string;
  is_active: boolean;
  ordre: number;
  /** Default VAT rate (percent, e.g. "20.00"); null = none. Honoured when régime on. */
  tva_taux: string | null;
}

export interface CreateCategorieInput {
  sens: Sens;
  libelle: string;
  compte_id?: string; // expert override; else auto (758/658)
  tva_taux?: string | null;
}

export interface UpdateCategorieInput {
  libelle?: string;
  compte_id?: string;
  ordre?: number;
  is_active?: boolean;
  tva_taux?: string | null;
}
