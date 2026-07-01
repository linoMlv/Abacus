import type { LigneEcriture } from '@/api/accounting';

export function today(): string {
  return new Date().toISOString().slice(0, 10);
}

/** The total amount of an entry (Σ debit = Σ credit), as a "0.00" string. */
export function entryAmount(lignes: LigneEcriture[]): string {
  return lignes.reduce((sum, l) => sum + Number(l.debit), 0).toFixed(2);
}
