import { api, apiUrl } from '../client';
import type {
  CreerEcritureDepuisLigneInput,
  ImportReleve,
  ImportReleveMapping,
  LigneBancaire,
  LigneBancaireStatut,
  RapprochementSuggestion,
} from './banque';
import type { Categorie, CreateCategorieInput, UpdateCategorieInput } from './categorie';
import type { Sens } from './common';
import type {
  CreateRecurrenceInput,
  GenerationResult,
  Recurrence,
  UpdateRecurrenceInput,
} from './recurrence';
import type {
  BulkResult,
  Ecriture,
  EcritureContenu,
  EcritureListItem,
  JournalFilters,
  Justificatif,
  SaisieSimpleInput,
  VirementInput,
} from './ecriture';
import type {
  CreateEvenementInput,
  Evenement,
  EvenementStatut,
  UpdateEvenementInput,
} from './evenement';
import type {
  AffectationResultat,
  ClotureResult,
  Compte,
  CompteTresorerie,
  CreateExerciceInput,
  CreateTresorerieInput,
  Exercice,
  Journal,
  UpdateTresorerieInput,
} from './referentiel';
import type { Synthese, SyntheseParams } from './synthese';
import type { Tiers, TypeTiers } from './tiers';
import type { EtatTva } from './tva';

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
  listExercices: (associationId: string) => api.get<Exercice[]>(`${base(associationId)}/exercices`),
  creerExercice: (associationId: string, input: CreateExerciceInput) =>
    api.post<Exercice>(`${base(associationId)}/exercices`, input),
  /** Close a fiscal year: determine the result, carry balances forward, lock it. */
  cloturerExercice: (associationId: string, exerciceId: string, affectation: AffectationResultat) =>
    api.post<ClotureResult>(`${base(associationId)}/exercices/${exerciceId}/cloture`, affectation),
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
  getEtatTva: (associationId: string, params: SyntheseParams = {}) =>
    api.get<EtatTva>(`${base(associationId)}/tva${qs({ ...params })}`),
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
  annexePdfUrl: (associationId: string, params: SyntheseParams = {}) =>
    apiUrl(`${base(associationId)}/exports/annexe.pdf${qs({ ...params })}`),
  fecUrl: (associationId: string, exerciceId?: string) =>
    apiUrl(`${base(associationId)}/exports/fec${qs({ exercice_id: exerciceId })}`),
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
  /** Edit a draft entry in place (same origine); the content variant must match. */
  modifierEcriture: (associationId: string, ecritureId: string, contenu: EcritureContenu) =>
    api.patch<Ecriture>(`${base(associationId)}/ecritures/${ecritureId}`, contenu),
  validerEcriture: (associationId: string, ecritureId: string) =>
    api.post<Ecriture>(`${base(associationId)}/ecritures/${ecritureId}/validation`),
  /**
   * Reverse a validated entry (contre-passation): creates a linked extourne draft.
   * With a `remplacement` (matching the original's origine), the corrected entry is
   * also booked as a draft in the same call (annule-et-remplace).
   */
  contrepasserEcriture: (
    associationId: string,
    ecritureId: string,
    body?: { remplacement?: EcritureContenu }
  ) =>
    api.post<{ extourne: Ecriture; remplacement: Ecriture | null }>(
      `${base(associationId)}/ecritures/${ecritureId}/contrepassation`,
      body
    ),
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

  // --- Banque : import & rapprochement (§5) ---
  listImportsReleve: (associationId: string, compteId?: string) =>
    api.get<ImportReleve[]>(`${base(associationId)}/banque/imports${qs({ compte_id: compteId })}`),
  importerReleve: (
    associationId: string,
    compteId: string,
    mapping: ImportReleveMapping,
    file: File
  ) => {
    const form = new FormData();
    form.append('compte_id', compteId);
    form.append('date_col', String(mapping.date_col));
    form.append('libelle_col', String(mapping.libelle_col));
    if (mapping.montant_col !== undefined) form.append('montant_col', String(mapping.montant_col));
    if (mapping.debit_col !== undefined) form.append('debit_col', String(mapping.debit_col));
    if (mapping.credit_col !== undefined) form.append('credit_col', String(mapping.credit_col));
    form.append('date_format', mapping.date_format);
    form.append('decimal_sep', mapping.decimal_sep);
    form.append('delimiter', mapping.delimiter);
    form.append('has_header', mapping.has_header ? 'true' : 'false');
    form.append('fichier', file);
    return api.postForm<ImportReleve>(`${base(associationId)}/banque/import`, form);
  },
  importerReleveOfx: (associationId: string, compteId: string, file: File) => {
    const form = new FormData();
    form.append('compte_id', compteId);
    form.append('fichier', file);
    return api.postForm<ImportReleve>(`${base(associationId)}/banque/import/ofx`, form);
  },
  supprimerImportReleve: (associationId: string, importId: string) =>
    api.del<void>(`${base(associationId)}/banque/imports/${importId}`),
  listLignesBancaires: (
    associationId: string,
    params: { compte_id?: string; statut?: LigneBancaireStatut; import_id?: string } = {}
  ) => api.get<LigneBancaire[]>(`${base(associationId)}/banque/lignes${qs({ ...params })}`),
  suggestionsRapprochement: (associationId: string, ligneId: string) =>
    api.get<RapprochementSuggestion[]>(
      `${base(associationId)}/banque/lignes/${ligneId}/suggestions`
    ),
  rapprocherLigne: (associationId: string, ligneId: string, ecritureId: string) =>
    api.post<LigneBancaire>(`${base(associationId)}/banque/lignes/${ligneId}/rapprocher`, {
      ecriture_id: ecritureId,
    }),
  creerEcritureDepuisLigne: (
    associationId: string,
    ligneId: string,
    input: CreerEcritureDepuisLigneInput
  ) => api.post<Ecriture>(`${base(associationId)}/banque/lignes/${ligneId}/creer-ecriture`, input),
  delettrerLigne: (associationId: string, ligneId: string) =>
    api.post<LigneBancaire>(`${base(associationId)}/banque/lignes/${ligneId}/delettrer`),
  ignorerLigne: (associationId: string, ligneId: string, ignore: boolean) =>
    api.post<LigneBancaire>(
      `${base(associationId)}/banque/lignes/${ligneId}/ignorer${qs({
        ignore: ignore ? 'true' : 'false',
      })}`
    ),

  // --- Récurrences (§5) ---
  listRecurrences: (associationId: string, actif?: boolean) =>
    api.get<Recurrence[]>(
      `${base(associationId)}/recurrences${qs({
        actif: actif === undefined ? undefined : String(actif),
      })}`
    ),
  creerRecurrence: (associationId: string, input: CreateRecurrenceInput) =>
    api.post<Recurrence>(`${base(associationId)}/recurrences`, input),
  modifierRecurrence: (associationId: string, recurrenceId: string, input: UpdateRecurrenceInput) =>
    api.patch<Recurrence>(`${base(associationId)}/recurrences/${recurrenceId}`, input),
  supprimerRecurrence: (associationId: string, recurrenceId: string) =>
    api.del<void>(`${base(associationId)}/recurrences/${recurrenceId}`),
  genererRecurrences: (associationId: string) =>
    api.post<GenerationResult>(`${base(associationId)}/recurrences/generer`),
};
