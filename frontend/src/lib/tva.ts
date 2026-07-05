/** VAT rates offered across the app ('0' = no VAT). Values are already normalized. */
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
