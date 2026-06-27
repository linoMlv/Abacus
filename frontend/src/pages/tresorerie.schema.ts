import { z } from 'zod';

import { amountToDecimalString } from './saisie.schema';

/** Opening balance: a signed amount (overdrafts allowed), or empty for none. */
const SIGNED_AMOUNT_PATTERN = /^-?\d+([.,]\d{1,2})?$/;

export const tresorerieSchema = z.object({
  nom: z.string().trim().min(1, 'Indiquez un nom.').max(120, 'Nom trop long (120 caractères max).'),
  type_tresorerie: z.enum(['banque', 'caisse', 'en_ligne', 'epargne', 'autre']),
  iban: z.string().trim().max(64, 'Identifiant trop long.'),
  solde_initial: z
    .string()
    .trim()
    .refine((v) => v === '' || SIGNED_AMOUNT_PATTERN.test(v), 'Montant invalide (ex. 500,00).')
    .refine(
      (v) => v === '' || Number(amountToDecimalString(v)) !== 0,
      'Le solde doit être non nul.'
    ),
  date_solde_initial: z.string(),
});

export type TresorerieForm = z.infer<typeof tresorerieSchema>;
