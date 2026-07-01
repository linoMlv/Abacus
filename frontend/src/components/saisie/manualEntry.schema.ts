import { z } from 'zod';

import type { Ecriture } from '@/api/accounting';
import { cents } from '@/lib/format';
import { MODE_REGLEMENT_VALUES } from '@/pages/saisie.schema';

/** Parse a French-typed amount string to a number (blank/invalid → 0). */
export function num(raw: string): number {
  const n = Number((raw ?? '').toString().replace(',', '.'));
  return Number.isFinite(n) ? n : 0;
}

/** Normalize an amount to the dot-decimal "0.00" string the API expects. */
export function toDecimal(raw: string): string {
  return num(raw).toFixed(2);
}

const lineSchema = z.object({
  compte_id: z.string(),
  debit: z.string(),
  credit: z.string(),
});

/**
 * The manual entry: a free, multi-line piece (expert). Each line carries a debit
 * or a credit on an account; Σdebit must equal Σcredit (the server re-checks). The
 * structural rules live here so the form blocks before reaching the API.
 */
export const manuelleSchema = z
  .object({
    journal_id: z.string().min(1, 'Choisissez un journal.'),
    date: z.string().min(1, 'Indiquez une date.'),
    libelle: z.string().trim().min(1, 'Indiquez un libellé.').max(200, 'Libellé trop long.'),
    reference_externe: z.string().trim().max(100, 'Référence trop longue.').optional(),
    mode_reglement: z.enum(['', ...MODE_REGLEMENT_VALUES]).optional(),
    lignes: z.array(lineSchema).min(2, 'Au moins deux lignes.'),
  })
  .superRefine((v, ctx) => {
    let totalDebit = 0;
    let totalCredit = 0;
    v.lignes.forEach((l, i) => {
      const d = num(l.debit);
      const c = num(l.credit);
      if (!l.compte_id) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ['lignes', i, 'compte_id'],
          message: 'Compte requis.',
        });
      }
      if (d > 0 && c > 0) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ['lignes', i, 'debit'],
          message: 'Un débit ou un crédit, pas les deux.',
        });
      } else if (d === 0 && c === 0) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ['lignes', i, 'debit'],
          message: 'Indiquez un montant.',
        });
      }
      totalDebit += d;
      totalCredit += c;
    });
    if (cents(totalDebit) !== cents(totalCredit)) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['lignes'],
        message: 'Le total des débits doit égaler le total des crédits.',
      });
    } else if (cents(totalDebit) === 0) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['lignes'],
        message: 'Le montant total doit être supérieur à 0.',
      });
    }
  });

export type ManuelleForm = z.infer<typeof manuelleSchema>;

/** Pre-fill the form from an existing entry (edit / correct). */
export function fromEntry(entry: Ecriture): ManuelleForm {
  return {
    journal_id: entry.journal_id,
    date: entry.date,
    libelle: entry.libelle ?? '',
    reference_externe: entry.reference_externe ?? '',
    mode_reglement: entry.mode_reglement ?? '',
    lignes: entry.lignes.map((l) => ({
      compte_id: l.compte_id,
      debit: Number(l.debit) > 0 ? l.debit : '',
      credit: Number(l.credit) > 0 ? l.credit : '',
    })),
  };
}
