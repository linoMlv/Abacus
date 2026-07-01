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
