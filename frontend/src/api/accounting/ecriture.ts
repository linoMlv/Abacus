import type { ModeReglement, TypeOperation } from './common';

export type EcritureStatut = 'brouillon' | 'validee';
export type EcritureOrigine =
  | 'saisie_simple'
  | 'virement'
  | 'manuelle'
  | 'import'
  | 'recurrence'
  | 'a_nouveau'
  | 'extourne'
  | 'cloture';

export interface LigneEcriture {
  id: string;
  compte_id: string;
  libelle: string;
  debit: string;
  credit: string;
  /** VAT rate/amount carried by the taxable-base (HT) line; null when no VAT. */
  tva_taux?: string | null;
  tva_montant?: string | null;
}

/** Common metadata shared by a journal row and a full entry. */
interface EcritureBase {
  id: string;
  exercice_id: string;
  journal_id: string;
  categorie_id: string | null;
  tiers_id: string | null;
  evenement_id: string | null;
  date: string;
  numero_piece: number;
  libelle: string;
  reference_externe: string | null;
  mode_reglement: ModeReglement | null;
  statut: EcritureStatut;
  origine: EcritureOrigine;
  extourne_de_id: string | null;
  created_at: string;
  validated_at: string | null;
}

/** A journal row: entry metadata plus its total and human journal code. */
export interface EcritureListItem extends EcritureBase {
  montant: string;
  journal_code: string;
}

/** A posted accounting entry with its balanced lines. */
export interface Ecriture extends EcritureBase {
  lignes: LigneEcriture[];
}

/** Metadata of a supporting document attached to an entry. */
export interface Justificatif {
  id: string;
  ecriture_id: string | null;
  filename: string;
  content_type: string;
  size: number;
  created_at: string;
}

/** Upload constraints, mirrored from the server (which re-validates). */
export const JUSTIFICATIF_MAX_BYTES = 5 * 1024 * 1024;
export const JUSTIFICATIF_ACCEPT = '.pdf,image/png,image/jpeg,image/gif,image/webp';

/**
 * Filters for the journal listing (all optional, all server-scoped). The
 * faceted filters take several values (OR within the facet); the facets still
 * compose with AND. Date range and text search complete them.
 */
export interface JournalFilters {
  statut?: EcritureStatut[];
  journal_id?: string[];
  compte_id?: string[];
  type_operation?: TypeOperation[];
  categorie_id?: string[];
  tiers_id?: string[];
  evenement_id?: string[];
  date_from?: string;
  date_to?: string;
  exercice_id?: string;
  q?: string;
  limit?: number;
  offset?: number;
}

/** Outcome of a best-effort bulk action: ids processed and ids ignored (with reason). */
export interface BulkResult {
  traitees: string[];
  ignorees: { id: string; raison: string }[];
}

/** Body of an assisted (simple) recette/dépense entry. Amount as a decimal string. */
export interface SaisieSimpleInput {
  categorie_id: string;
  compte_tresorerie_id: string;
  montant: string;
  date: string;
  libelle?: string;
  tiers_id?: string;
  evenement_id?: string;
  reference_externe?: string;
  mode_reglement?: ModeReglement;
  /** VAT rate override (percent). Honoured only when the régime is on. */
  tva_taux?: string;
}

/** One line of a manual multi-line entry: a debit or a credit on an account. */
export interface LigneInput {
  compte_id: string;
  libelle?: string;
  debit: string;
  credit: string;
}

/** Body of a manual multi-line entry; Σdebit must equal Σcredit (server-validated). */
export interface SaisieManuelleInput {
  journal_id: string;
  date: string;
  libelle: string;
  lignes: LigneInput[];
  tiers_id?: string;
  evenement_id?: string;
  reference_externe?: string;
  mode_reglement?: ModeReglement;
}

/** Body of an internal transfer between two treasury accounts. */
export interface VirementInput {
  compte_source_id: string;
  compte_destination_id: string;
  montant: string;
  date: string;
  libelle?: string;
  reference_externe?: string;
  mode_reglement?: ModeReglement;
}

/**
 * Origine-specific entry content; exactly one variant is set. Reused for editing
 * a draft in place (PATCH) and for the replacement of an annule-et-remplace; the
 * variant must match the entry's origine.
 */
export interface EcritureContenu {
  simple?: SaisieSimpleInput;
  virement?: VirementInput;
  manuelle?: SaisieManuelleInput;
}
