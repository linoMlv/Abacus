// Historically a single `api/accounting.ts` module. Split by domain (common,
// categorie, tiers, referentiel, ecriture, evenement, synthese) plus the client;
// this barrel re-exports everything so `@/api/accounting` imports are unchanged.
export * from './common';
export * from './annexe';
export * from './categorie';
export * from './banque';
export * from './recurrence';
export * from './tiers';
export * from './referentiel';
export * from './plan';
export * from './ecriture';
export * from './evenement';
export * from './synthese';
export * from './tva';
export { accountingApi } from './client';
