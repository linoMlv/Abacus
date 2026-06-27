import { describe, it, expect } from 'vitest';

import { amountToDecimalString, saisieSchema } from '@/pages/saisie.schema';

const valid = {
  sens: 'recette' as const,
  categorie_id: 'cat',
  compte_tresorerie_id: 'tres',
  montant: '150,00',
  date: '2026-06-27',
};

describe('saisieSchema', () => {
  it('accepts a well-formed entry', () => {
    expect(saisieSchema.safeParse(valid).success).toBe(true);
  });

  it('rejects an empty amount', () => {
    expect(saisieSchema.safeParse({ ...valid, montant: '' }).success).toBe(false);
  });

  it('rejects a malformed amount', () => {
    expect(saisieSchema.safeParse({ ...valid, montant: '12.345' }).success).toBe(false);
    expect(saisieSchema.safeParse({ ...valid, montant: 'abc' }).success).toBe(false);
    expect(saisieSchema.safeParse({ ...valid, montant: '1 000' }).success).toBe(false);
  });

  it('rejects a non-positive amount', () => {
    expect(saisieSchema.safeParse({ ...valid, montant: '0' }).success).toBe(false);
    expect(saisieSchema.safeParse({ ...valid, montant: '0,00' }).success).toBe(false);
  });

  it('requires a category and a treasury account', () => {
    expect(saisieSchema.safeParse({ ...valid, categorie_id: '' }).success).toBe(false);
    expect(saisieSchema.safeParse({ ...valid, compte_tresorerie_id: '' }).success).toBe(false);
  });
});

describe('amountToDecimalString', () => {
  it('normalizes a French comma to a dot and trims', () => {
    expect(amountToDecimalString('150,00')).toBe('150.00');
    expect(amountToDecimalString('  9,5 ')).toBe('9.5');
    expect(amountToDecimalString('42')).toBe('42');
  });
});
