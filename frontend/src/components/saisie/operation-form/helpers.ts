import type { LigneEcriture } from '@/api/accounting';

export function today(): string {
  return new Date().toISOString().slice(0, 10);
}

/** The total amount of an entry (Σ debit = Σ credit), as a "0.00" string. */
export function entryAmount(lignes: LigneEcriture[]): string {
  return lignes.reduce((sum, l) => sum + Number(l.debit), 0).toFixed(2);
}

/** VAT rates offered at saisie ('0' = no VAT). Values match the normalized form. */
export const TVA_TAUX_OPTIONS: { value: string; label: string }[] = [
  { value: '0', label: 'Sans TVA' },
  { value: '2.1', label: '2,1 %' },
  { value: '5.5', label: '5,5 %' },
  { value: '10', label: '10 %' },
  { value: '20', label: '20 %' },
];

/** Normalize a rate string ("20.00" → "20", "5.50" → "5.5") to match option values. */
export function normalizeTaux(taux: string | null | undefined): string {
  if (taux == null || taux === '') return '0';
  return String(Number(taux));
}

/** The VAT rate carried by an entry's taxable-base line ('0' if none), normalized. */
export function entryTvaTaux(lignes: LigneEcriture[]): string {
  const base = lignes.find((l) => l.tva_taux != null);
  return normalizeTaux(base?.tva_taux);
}
