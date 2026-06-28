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

export interface CreateCategorieInput {
  sens: Sens;
  libelle: string;
  compte_id?: string; // expert override; else auto (758/658)
}

export interface UpdateCategorieInput {
  libelle?: string;
  compte_id?: string;
  ordre?: number;
  is_active?: boolean;
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

/** Kind of a named treasury account (where the money is), mirrors the backend. */
export type TypeTresorerie = 'banque' | 'caisse' | 'en_ligne' | 'epargne' | 'autre';

/** A named treasury account with its current balance (decimal string). */
export interface CompteTresorerie {
  id: string;
  numero: string;
  libelle: string;
  type_tresorerie: TypeTresorerie;
  iban: string | null;
  couleur: string | null;
  ordre: number;
  is_active: boolean;
  solde: string;
}

export interface CreateTresorerieInput {
  nom: string;
  type_tresorerie: TypeTresorerie;
  iban?: string;
  couleur?: string;
  solde_initial?: string;
  date_solde_initial?: string;
}

export interface UpdateTresorerieInput {
  nom?: string;
  type_tresorerie?: TypeTresorerie;
  iban?: string;
  couleur?: string;
  ordre?: number;
  is_active?: boolean;
}

/** Human labels for the treasury account types. */
export const TYPE_TRESORERIE_LABELS: Record<TypeTresorerie, string> = {
  banque: 'Banque',
  caisse: 'Caisse',
  en_ligne: 'En ligne',
  epargne: 'Épargne',
  autre: 'Autre',
};

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
  compte_id?: string;
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

const base = (associationId: string) => `/asso/${associationId}`;

/** Build a query string from defined, non-empty params (else empty). */
function qs(params: Record<string, string | number | undefined>): string {
  const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== '');
  if (entries.length === 0) return '';
  return '?' + entries.map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`).join('&');
}

export const accountingApi = {
  listCategories: (associationId: string, sens?: Sens, includeInactive = false) =>
    api.get<Categorie[]>(
      `${base(associationId)}/categories${qs({
        sens,
        include_inactive: includeInactive ? 'true' : undefined,
      })}`
    ),
  creerCategorie: (associationId: string, input: CreateCategorieInput) =>
    api.post<Categorie>(`${base(associationId)}/categories`, input),
  modifierCategorie: (associationId: string, categorieId: string, input: UpdateCategorieInput) =>
    api.patch<Categorie>(`${base(associationId)}/categories/${categorieId}`, input),
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
  listTresorerie: (associationId: string, includeInactive = false) =>
    api.get<CompteTresorerie[]>(
      `${base(associationId)}/tresorerie${includeInactive ? '?include_inactive=true' : ''}`
    ),
  creerCompteTresorerie: (associationId: string, input: CreateTresorerieInput) =>
    api.post<CompteTresorerie>(`${base(associationId)}/tresorerie`, input),
  modifierCompteTresorerie: (
    associationId: string,
    compteId: string,
    input: UpdateTresorerieInput
  ) => api.patch<CompteTresorerie>(`${base(associationId)}/tresorerie/${compteId}`, input),
  definirSoldeInitial: (
    associationId: string,
    compteId: string,
    input: { montant: string; date_solde_initial?: string }
  ) =>
    api.post<CompteTresorerie>(
      `${base(associationId)}/tresorerie/${compteId}/solde-initial`,
      input
    ),
};
