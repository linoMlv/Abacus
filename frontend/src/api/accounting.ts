import { api } from './client';

/** Direction of an assisted entry, mirrors the backend `SensCategorie`. */
export type Sens = 'recette' | 'depense';

export type CompteType = 'actif' | 'passif' | 'charge' | 'produit';
export type EcritureStatut = 'brouillon' | 'validee';
export type EcritureOrigine = 'saisie_simple' | 'manuelle' | 'import' | 'recurrence';

/** A plain-language entry category bridging the simple screen to an account. */
export interface Categorie {
  id: string;
  sens: Sens;
  libelle: string;
  compte_id: string;
  journal_id: string;
  is_active: boolean;
  ordre: number;
}

/** One account of the chart of accounts. */
export interface Compte {
  id: string;
  numero: string;
  libelle: string;
  classe: number;
  type: CompteType;
  is_active: boolean;
}

/** One journal (book): BQ, CA, AC, VE, OD… */
export interface Journal {
  id: string;
  code: string;
  libelle: string;
}

export interface LigneEcriture {
  id: string;
  compte_id: string;
  libelle: string;
  debit: string;
  credit: string;
}

/** Common metadata shared by a journal row and a full entry. */
interface EcritureBase {
  id: string;
  exercice_id: string;
  journal_id: string;
  date: string;
  numero_piece: number;
  libelle: string;
  statut: EcritureStatut;
  origine: EcritureOrigine;
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

/** Filters for the journal listing (all optional, all server-scoped). */
export interface JournalFilters {
  statut?: EcritureStatut;
  journal_id?: string;
  exercice_id?: string;
  q?: string;
  limit?: number;
  offset?: number;
}

/** Body of an assisted (simple) recette/dépense entry. Amount as a decimal string. */
export interface SaisieSimpleInput {
  categorie_id: string;
  compte_tresorerie_id: string;
  montant: string;
  date: string;
  libelle?: string;
}

/** Comptes de trésorerie (classe 5: 512 banque, 531 caisse…) used as counterpart. */
export const CLASSE_TRESORERIE = 5;

const base = (associationId: string) => `/asso/${associationId}`;

/** Build a query string from defined, non-empty params (else empty). */
function qs(params: Record<string, string | number | undefined>): string {
  const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== '');
  if (entries.length === 0) return '';
  return '?' + entries.map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`).join('&');
}

export const accountingApi = {
  listCategories: (associationId: string, sens?: Sens) =>
    api.get<Categorie[]>(`${base(associationId)}/categories${sens ? `?sens=${sens}` : ''}`),
  listComptes: (associationId: string, classe?: number) =>
    api.get<Compte[]>(`${base(associationId)}/comptes${classe ? `?classe=${classe}` : ''}`),
  listJournaux: (associationId: string) => api.get<Journal[]>(`${base(associationId)}/journaux`),
  creerSaisieSimple: (associationId: string, input: SaisieSimpleInput) =>
    api.post<Ecriture>(`${base(associationId)}/ecritures/simple`, input),
  listEcritures: (associationId: string, filters: JournalFilters = {}) =>
    api.get<EcritureListItem[]>(`${base(associationId)}/ecritures${qs({ ...filters })}`),
  getEcriture: (associationId: string, ecritureId: string) =>
    api.get<Ecriture>(`${base(associationId)}/ecritures/${ecritureId}`),
  validerEcriture: (associationId: string, ecritureId: string) =>
    api.post<Ecriture>(`${base(associationId)}/ecritures/${ecritureId}/validation`),
  supprimerEcriture: (associationId: string, ecritureId: string) =>
    api.del<void>(`${base(associationId)}/ecritures/${ecritureId}`),
};
