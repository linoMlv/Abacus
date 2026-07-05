import type { LigneEcriture } from '@/api/accounting';
import { normalizeTaux } from '@/lib/tva';

export function today(): string {
  return new Date().toISOString().slice(0, 10);
}

/** The total amount of an entry (Σ debit = Σ credit), as a "0.00" string. */
export function entryAmount(lignes: LigneEcriture[]): string {
  return lignes.reduce((sum, l) => sum + Number(l.debit), 0).toFixed(2);
}

/** The VAT rate carried by an entry's taxable-base line ('0' if none), normalized. */
export function entryTvaTaux(lignes: LigneEcriture[]): string {
  const base = lignes.find((l) => l.tva_taux != null);
  return normalizeTaux(base?.tva_taux);
}
