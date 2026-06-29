import { api, apiUrl } from './client';

/** Direction of an assisted entry, mirrors the backend `SensCategorie`. */
export type Sens = 'recette' | 'depense';

/** Operation type used by the journal filter (type-first vocabulary, §15.3). */
export type TypeOperation = 'recette' | 'depense' | 'virement';

/** Human labels for the operation types. */
export const TYPE_OPERATION_LABELS: Record<TypeOperation, string> = {
  recette: 'Recette',
  depense: 'Dépense',
  virement: 'Virement',
};

export type CompteType = 'actif' | 'passif' | 'charge' | 'produit';
export type EcritureStatut = 'brouillon' | 'validee';
export type EcritureOrigine =
  | 'saisie_simple'
  | 'virement'
  | 'manuelle'
  | 'import'
  | 'recurrence'
  | 'a_nouveau';

/** Informative payment method on an entry, mirrors the backend `ModeReglement`. */
export type ModeReglement = 'carte' | 'cheque' | 'especes' | 'virement' | 'prelevement' | 'autre';

/** Human labels for the payment methods. */
export const MODE_REGLEMENT_LABELS: Record<ModeReglement, string> = {
  carte: 'Carte',
  cheque: 'Chèque',
  especes: 'Espèces',
  virement: 'Virement',
  prelevement: 'Prélèvement',
  autre: 'Autre',
};

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
  reference_externe: string | null;
  mode_reglement: ModeReglement | null;
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
}

/** Lifecycle of an event, mirrors the backend `EvenementStatut`. */
export type EvenementStatut = 'actif' | 'cloture';

export const EVENEMENT_STATUT_LABELS: Record<EvenementStatut, string> = {
  actif: 'Actif',
  cloture: 'Clôturé',
};

/** An analytic event with its budget and computed réalisé (decimal strings). */
export interface Evenement {
  id: string;
  nom: string;
  description: string | null;
  date_debut: string | null;
  date_fin: string | null;
  budget_recettes: string | null;
  budget_depenses: string | null;
  statut: EvenementStatut;
  couleur: string | null;
  realise_recettes: string;
  realise_depenses: string;
  resultat: string;
}

export interface CreateEvenementInput {
  nom: string;
  description?: string;
  date_debut?: string;
  date_fin?: string;
  budget_recettes?: string;
  budget_depenses?: string;
  couleur?: string;
}

export interface UpdateEvenementInput extends Partial<CreateEvenementInput> {
  statut?: EvenementStatut;
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

/** Consolidated dashboard payload (T6). All amounts are decimal strings. */
export interface SyntheseResultat {
  recettes: string;
  depenses: string;
  resultat: string;
}

export interface RepartitionCategorie {
  categorie_id: string;
  libelle: string;
  sens: Sens;
  montant: string;
}

export interface RepartitionEvenement {
  evenement_id: string;
  nom: string;
  couleur: string | null;
  recettes: string;
  depenses: string;
  resultat: string;
}

export interface CourbePoint {
  date: string;
  solde: string;
}

export interface AlerteEvenement {
  evenement_id: string;
  nom: string;
  budget_depenses: string;
  realise_depenses: string;
}

export interface AlerteExercice {
  exercice_id: string;
  libelle: string;
  date_fin: string;
}

export interface SyntheseAlertes {
  brouillons: number;
  evenements_depasses: AlerteEvenement[];
  exercices_a_cloturer: AlerteExercice[];
}

export interface Synthese {
  date_from: string;
  date_to: string;
  resultat: SyntheseResultat;
  repartition_categories: RepartitionCategorie[];
  repartition_evenements: RepartitionEvenement[];
  courbe_tresorerie: CourbePoint[];
  alertes: SyntheseAlertes;
}

/** Period for the synthesis; omit both to let the server use the open exercice. */
export interface SyntheseParams {
  date_from?: string;
  date_to?: string;
}

const base = (associationId: string) => `/asso/${associationId}`;

/** Build a query string from defined, non-empty params (else empty). */
function qs(params: Record<string, string | number | string[] | undefined>): string {
  const parts: string[] = [];
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === '') continue;
    // An array emits one repeated param per value (?k=a&k=b), the multi-value form.
    const values = Array.isArray(v) ? v : [v];
    for (const value of values) {
      if (value === undefined || value === '') continue;
      parts.push(`${k}=${encodeURIComponent(String(value))}`);
    }
  }
  return parts.length === 0 ? '' : '?' + parts.join('&');
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
  creerVirement: (associationId: string, input: VirementInput) =>
    api.post<Ecriture>(`${base(associationId)}/ecritures/virement`, input),
  listTiers: (associationId: string, type?: TypeTiers) =>
    api.get<Tiers[]>(`${base(associationId)}/tiers${qs({ type })}`),
  creerTiers: (associationId: string, input: { nom: string; type: TypeTiers }) =>
    api.post<Tiers>(`${base(associationId)}/tiers`, input),
  getSynthese: (associationId: string, params: SyntheseParams = {}) =>
    api.get<Synthese>(`${base(associationId)}/synthese${qs({ ...params })}`),
  // Export download URLs (server streams an attachment; the cookie session is
  // sent automatically on a same-origin navigation, so a plain link works).
  // The journal export follows the active journal filters (item 8), not just the period.
  journalPdfUrl: (associationId: string, filters: JournalFilters = {}) =>
    apiUrl(`${base(associationId)}/exports/journal.pdf${qs({ ...filters })}`),
  journalXlsxUrl: (associationId: string, filters: JournalFilters = {}) =>
    apiUrl(`${base(associationId)}/exports/journal.xlsx${qs({ ...filters })}`),
  grandLivrePdfUrl: (associationId: string, params: SyntheseParams = {}) =>
    apiUrl(`${base(associationId)}/exports/grand-livre.pdf${qs({ ...params })}`),
  grandLivreXlsxUrl: (associationId: string, params: SyntheseParams = {}) =>
    apiUrl(`${base(associationId)}/exports/grand-livre.xlsx${qs({ ...params })}`),
  relevePdfUrl: (associationId: string, compteId: string, params: SyntheseParams = {}) =>
    apiUrl(`${base(associationId)}/exports/tresorerie/${compteId}/releve.pdf${qs({ ...params })}`),
  compteResultatPdfUrl: (associationId: string, params: SyntheseParams = {}) =>
    apiUrl(`${base(associationId)}/exports/compte-resultat.pdf${qs({ ...params })}`),
  bilanPdfUrl: (associationId: string, params: SyntheseParams = {}) =>
    apiUrl(`${base(associationId)}/exports/bilan.pdf${qs({ ...params })}`),
  evenementBilanPdfUrl: (associationId: string, evenementId: string) =>
    apiUrl(`${base(associationId)}/exports/evenements/${evenementId}/bilan.pdf`),
  listEvenements: (associationId: string, statut?: EvenementStatut) =>
    api.get<Evenement[]>(`${base(associationId)}/evenements${qs({ statut })}`),
  getEvenement: (associationId: string, evenementId: string) =>
    api.get<Evenement>(`${base(associationId)}/evenements/${evenementId}`),
  creerEvenement: (associationId: string, input: CreateEvenementInput) =>
    api.post<Evenement>(`${base(associationId)}/evenements`, input),
  modifierEvenement: (associationId: string, evenementId: string, input: UpdateEvenementInput) =>
    api.patch<Evenement>(`${base(associationId)}/evenements/${evenementId}`, input),
  listJustificatifs: (associationId: string, ecritureId: string) =>
    api.get<Justificatif[]>(`${base(associationId)}/ecritures/${ecritureId}/justificatifs`),
  uploadJustificatif: (associationId: string, ecritureId: string, file: File) => {
    const form = new FormData();
    form.append('file', file);
    return api.postForm<Justificatif>(
      `${base(associationId)}/ecritures/${ecritureId}/justificatifs`,
      form
    );
  },
  supprimerJustificatif: (associationId: string, justificatifId: string) =>
    api.del<void>(`${base(associationId)}/justificatifs/${justificatifId}`),
  justificatifContenuUrl: (associationId: string, justificatifId: string) =>
    apiUrl(`${base(associationId)}/justificatifs/${justificatifId}/contenu`),
  justificatifApercuUrl: (associationId: string, justificatifId: string) =>
    apiUrl(`${base(associationId)}/justificatifs/${justificatifId}/apercu`),
  listEcritures: (associationId: string, filters: JournalFilters = {}) =>
    api.get<EcritureListItem[]>(`${base(associationId)}/ecritures${qs({ ...filters })}`),
  getEcriture: (associationId: string, ecritureId: string) =>
    api.get<Ecriture>(`${base(associationId)}/ecritures/${ecritureId}`),
  validerEcriture: (associationId: string, ecritureId: string) =>
    api.post<Ecriture>(`${base(associationId)}/ecritures/${ecritureId}/validation`),
  supprimerEcriture: (associationId: string, ecritureId: string) =>
    api.del<void>(`${base(associationId)}/ecritures/${ecritureId}`),
  validerEcrituresGroupe: (associationId: string, ids: string[]) =>
    api.post<BulkResult>(`${base(associationId)}/ecritures/validation-groupee`, { ids }),
  supprimerEcrituresGroupe: (associationId: string, ids: string[]) =>
    api.post<BulkResult>(`${base(associationId)}/ecritures/suppression-groupee`, { ids }),
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
