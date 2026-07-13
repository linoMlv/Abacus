/** Chart of accounts: guided edition, balance, ledger and reconciliation state. */

import type { CompteType } from './common';

/** Create an account: guided (`prefixe` → next free child) or expert (`numero`). */
export interface CreateCompteInput {
  libelle: string;
  type: CompteType;
  numero?: string;
  prefixe?: string;
}

/** Rename and/or archive. The number is immutable once created. */
export interface UpdateCompteInput {
  libelle?: string;
  is_active?: boolean;
}

/** One line of the trial balance (decimal strings). */
export interface BalanceCompte {
  compte_id: string;
  numero: string;
  libelle: string;
  total_debit: string;
  total_credit: string;
  solde: string;
}

/** One movement of an account's ledger, with the running balance. */
export interface GrandLivreLigne {
  ecriture_id: string;
  date: string;
  numero_piece: number;
  journal_id: string;
  libelle: string;
  debit: string;
  credit: string;
  solde: string;
}

/** Reconciliation state of one treasury account (books vs. bank). */
export interface RapprochementCompte {
  compte_id: string;
  numero: string;
  libelle: string;
  solde_comptable: string;
  nb_non_rapprochees: number;
  montant_non_rapproche: string;
  solde_bancaire_estime: string;
  dernier_import: string | null;
}

/** Filters of the chart-of-accounts listing. */
export interface CompteFilters {
  classe?: number;
  includeInactive?: boolean;
  search?: string;
}

/** The accounting classes, in plain language first (C4: no jargon by default). */
export const CLASSES: { classe: number; label: string; hint: string }[] = [
  { classe: 1, label: 'Fonds propres et emprunts', hint: 'Réserves, report à nouveau, dettes' },
  { classe: 2, label: 'Investissements', hint: 'Matériel, mobilier, logiciels' },
  { classe: 3, label: 'Stocks', hint: 'Marchandises détenues' },
  { classe: 4, label: 'Tiers', hint: 'Fournisseurs, adhérents, TVA, salaires' },
  { classe: 5, label: 'Trésorerie', hint: 'Banque, caisse, épargne' },
  { classe: 6, label: 'Dépenses', hint: 'Charges : achats, loyers, assurances' },
  { classe: 7, label: 'Recettes', hint: 'Produits : cotisations, dons, subventions' },
  { classe: 8, label: 'Contributions en nature', hint: 'Bénévolat, dons en nature' },
];

/** Natures an account of this classe may carry (mirrors the backend rule). */
export function typesForClasse(classe: number): CompteType[] {
  if (classe === 6) return ['charge'];
  if (classe === 7) return ['produit'];
  if (classe === 8) return ['charge', 'produit'];
  return ['actif', 'passif'];
}

export const COMPTE_TYPE_LABELS: Record<CompteType, string> = {
  actif: 'Actif (ce que l’asso possède)',
  passif: 'Passif (ce que l’asso doit)',
  charge: 'Charge (une dépense)',
  produit: 'Produit (une recette)',
};
