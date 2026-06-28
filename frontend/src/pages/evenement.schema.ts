import { z } from 'zod';

/** A positive amount with up to two decimals, or empty (optional budget). */
const AMOUNT_PATTERN = /^\d+([.,]\d{1,2})?$/;

const optionalAmount = z
  .string()
  .trim()
  .optional()
  .refine((v) => !v || AMOUNT_PATTERN.test(v), 'Montant invalide (ex. 1500,00).');

export const evenementSchema = z
  .object({
    nom: z.string().trim().min(1, 'Le nom est requis.').max(120, 'Nom trop long.'),
    description: z.string().trim().max(500, 'Description trop longue.').optional(),
    date_debut: z.string().optional(),
    date_fin: z.string().optional(),
    budget_recettes: optionalAmount,
    budget_depenses: optionalAmount,
    couleur: z.string().optional(),
  })
  .refine((v) => !v.date_debut || !v.date_fin || v.date_fin >= v.date_debut, {
    path: ['date_fin'],
    message: 'La date de fin doit suivre la date de début.',
  });

export type EvenementForm = z.infer<typeof evenementSchema>;
