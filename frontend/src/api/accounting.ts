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

export interface LigneEcriture {
  id: string;
  compte_id: string;
  libelle: string;
  debit: string;
  credit: string;
}

/** A posted accounting entry with its balanced lines. */
export interface Ecriture {
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
  lignes: LigneEcriture[];
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

export const accountingApi = {
  listCategories: (associationId: string, sens?: Sens) =>
    api.get<Categorie[]>(`${base(associationId)}/categories${sens ? `?sens=${sens}` : ''}`),
  listComptes: (associationId: string, classe?: number) =>
    api.get<Compte[]>(`${base(associationId)}/comptes${classe ? `?classe=${classe}` : ''}`),
  creerSaisieSimple: (associationId: string, input: SaisieSimpleInput) =>
    api.post<Ecriture>(`${base(associationId)}/ecritures/simple`, input),
};
