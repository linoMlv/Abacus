/** Kind of third party, mirrors the backend `TypeTiers`. */
export type TypeTiers = 'fournisseur' | 'client' | 'donateur' | 'financeur' | 'autre';

/** A third party the association deals with (informative tag for now). */
export interface Tiers {
  id: string;
  type: TypeTiers;
  nom: string;
  adresse: string | null;
  code_postal: string | null;
  ville: string | null;
  is_active: boolean;
}

export interface CreateTiersInput {
  nom: string;
  type: TypeTiers;
  adresse?: string | null;
  code_postal?: string | null;
  ville?: string | null;
}

export interface UpdateTiersInput {
  nom?: string;
  type?: TypeTiers;
  adresse?: string | null;
  code_postal?: string | null;
  ville?: string | null;
  is_active?: boolean;
}

/** Human labels for the third-party types. */
export const TYPE_TIERS_LABELS: Record<TypeTiers, string> = {
  fournisseur: 'Fournisseur',
  client: 'Adhérent / client',
  donateur: 'Donateur',
  financeur: 'Financeur',
  autre: 'Autre',
};
