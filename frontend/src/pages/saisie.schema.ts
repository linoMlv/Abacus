import { z } from 'zod';

/** Accepts a French-typed amount: digits with an optional comma/dot and up to
 *  two decimals (e.g. "150", "150,5", "1234.56"). No thousands separators. */
const AMOUNT_PATTERN = /^\d+([.,]\d{1,2})?$/;

/** Payment methods, mirrors the backend `ModeReglement` (plus '' = none). */
export const MODE_REGLEMENT_VALUES = [
  'carte',
  'cheque',
  'especes',
  'virement',
  'prelevement',
  'autre',
] as const;

/** Normalize a validated amount to the dot-decimal string the API expects. */
export function amountToDecimalString(raw: string): string {
  return raw.trim().replace(',', '.');
}

const amount = z
  .string()
  .trim()
  .min(1, 'Indiquez un montant.')
  .regex(AMOUNT_PATTERN, 'Montant invalide (ex. 150,00).')
  .refine((v) => Number(amountToDecimalString(v)) > 0, 'Le montant doit être supérieur à 0.');

/**
 * One schema for the type-first entry screen. The base fields are always
 * present; which references are required depends on the operation type
 * (recette/dépense need a category + treasury account; a virement needs a
 * distinct source and destination). Advanced fields are all optional.
 */
export const saisieSchema = z
  .object({
    type: z.enum(['recette', 'depense', 'virement']),
    // Recette / dépense
    categorie_id: z.string(),
    compte_tresorerie_id: z.string(),
    // Virement
    compte_source_id: z.string(),
    compte_destination_id: z.string(),
    // Common
    montant: amount,
    date: z.string().min(1, 'Indiquez une date.'),
    // Avancé (optional)
    libelle: z.string().trim().max(200, 'Libellé trop long (200 caractères max).').optional(),
    reference_externe: z
      .string()
      .trim()
      .max(100, 'Référence trop longue (100 caractères max).')
      .optional(),
    mode_reglement: z.enum(['', ...MODE_REGLEMENT_VALUES]).optional(),
  })
  .superRefine((v, ctx) => {
    if (v.type === 'virement') {
      if (!v.compte_source_id) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ['compte_source_id'],
          message: 'Choisissez le compte de départ.',
        });
      }
      if (!v.compte_destination_id) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ['compte_destination_id'],
          message: "Choisissez le compte d'arrivée.",
        });
      }
      if (v.compte_source_id && v.compte_source_id === v.compte_destination_id) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ['compte_destination_id'],
          message: "Le compte d'arrivée doit être différent du compte de départ.",
        });
      }
    } else {
      if (!v.categorie_id) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ['categorie_id'],
          message: 'Choisissez une catégorie.',
        });
      }
      if (!v.compte_tresorerie_id) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ['compte_tresorerie_id'],
          message: 'Choisissez un compte de trésorerie.',
        });
      }
    }
  });

export type SaisieForm = z.infer<typeof saisieSchema>;
