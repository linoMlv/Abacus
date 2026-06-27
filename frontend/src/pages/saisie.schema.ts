import { z } from 'zod';

/** Accepts a French-typed amount: digits with an optional comma/dot and up to
 *  two decimals (e.g. "150", "150,5", "1234.56"). No thousands separators. */
const AMOUNT_PATTERN = /^\d+([.,]\d{1,2})?$/;

/** Normalize a validated amount to the dot-decimal string the API expects. */
export function amountToDecimalString(raw: string): string {
  return raw.trim().replace(',', '.');
}

export const saisieSchema = z.object({
  sens: z.enum(['recette', 'depense']),
  categorie_id: z.string().min(1, 'Choisissez une catégorie.'),
  compte_tresorerie_id: z.string().min(1, 'Choisissez un compte de trésorerie.'),
  montant: z
    .string()
    .trim()
    .min(1, 'Indiquez un montant.')
    .regex(AMOUNT_PATTERN, 'Montant invalide (ex. 150,00).')
    .refine((v) => Number(amountToDecimalString(v)) > 0, 'Le montant doit être supérieur à 0.'),
  date: z.string().min(1, 'Indiquez une date.'),
  libelle: z.string().trim().max(200, 'Libellé trop long (200 caractères max).').optional(),
});

export type SaisieForm = z.infer<typeof saisieSchema>;
