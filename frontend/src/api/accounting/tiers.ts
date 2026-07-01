/** Kind of third party, mirrors the backend `TypeTiers`. */
export type TypeTiers = 'fournisseur' | 'client' | 'donateur' | 'financeur' | 'autre';

/** A third party the association deals with (informative tag for now). */
export interface Tiers {
  id: string;
  type: TypeTiers;
  nom: string;
  is_active: boolean;
}

/** Human labels for the third-party types. */
export const TYPE_TIERS_LABELS: Record<TypeTiers, string> = {
  fournisseur: 'Fournisseur',
  client: 'Adhérent / client',
  donateur: 'Donateur',
  financeur: 'Financeur',
  autre: 'Autre',
};
