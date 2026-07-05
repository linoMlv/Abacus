import { api, apiUrl } from './client';

export type FormeDon = 'numeraire' | 'titres' | 'autre';

export const FORME_DON_LABELS: Record<FormeDon, string> = {
  numeraire: 'Numéraire',
  titres: 'Titres de sociétés',
  autre: 'Autre (frais, nature…)',
};

/** A donation eligible for a receipt: a validated recette with a donor. */
export interface Don {
  ecriture_id: string;
  date: string;
  numero_piece: number;
  libelle: string;
  montant: string;
  tiers_id: string;
  tiers_nom: string;
  recu_id: string | null;
  recu_numero: number | null;
}

/** An issued donation tax receipt. */
export interface RecuFiscal {
  id: string;
  numero: number;
  tiers_id: string;
  tiers_nom: string;
  date: string;
  annee: number;
  montant: string;
  forme: FormeDon;
  mode_reglement: string | null;
  annule: boolean;
}

export interface CreerRecuInput {
  tiers_id: string;
  ecriture_ids: string[];
  date: string;
  annee: number;
  forme: FormeDon;
  mode_reglement?: string;
}

const base = (associationId: string) => `/asso/${associationId}`;

export const donsApi = {
  listDons: (associationId: string, params: { annee?: number; non_recu?: boolean } = {}) => {
    const q = new URLSearchParams();
    if (params.annee != null) q.set('annee', String(params.annee));
    if (params.non_recu) q.set('non_recu', 'true');
    const suffix = q.toString() ? `?${q}` : '';
    return api.get<Don[]>(`${base(associationId)}/dons${suffix}`);
  },
  listRecus: (associationId: string) => api.get<RecuFiscal[]>(`${base(associationId)}/recus`),
  creerRecu: (associationId: string, input: CreerRecuInput) =>
    api.post<RecuFiscal>(`${base(associationId)}/recus`, input),
  supprimerRecu: (associationId: string, recuId: string) =>
    api.del<void>(`${base(associationId)}/recus/${recuId}`),
  recuPdfUrl: (associationId: string, recuId: string) =>
    apiUrl(`${base(associationId)}/recus/${recuId}/pdf`),
};
