import { describe, expect, it } from 'vitest';

import { amountToDecimalString, saisieSchema } from '@/pages/saisie.schema';

const valid = {
  type: 'recette' as const,
  categorie_id: 'cat',
  compte_tresorerie_id: 'tres',
  compte_source_id: '',
  compte_destination_id: '',
  montant: '150,00',
  date: '2026-06-27',
};

const validVirement = {
  type: 'virement' as const,
  categorie_id: '',
  compte_tresorerie_id: '',
  compte_source_id: 'caisse',
  compte_destination_id: 'banque',
  montant: '200',
  date: '2026-06-27',
};

describe('saisieSchema', () => {
  it('accepts a well-formed recette and virement', () => {
    expect(saisieSchema.safeParse(valid).success).toBe(true);
    expect(saisieSchema.safeParse(validVirement).success).toBe(true);
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

  it('requires a category and a treasury account for recette/dépense', () => {
    expect(saisieSchema.safeParse({ ...valid, categorie_id: '' }).success).toBe(false);
    expect(saisieSchema.safeParse({ ...valid, compte_tresorerie_id: '' }).success).toBe(false);
  });

  it('requires a distinct source and destination for a virement', () => {
    expect(saisieSchema.safeParse({ ...validVirement, compte_source_id: '' }).success).toBe(false);
    expect(saisieSchema.safeParse({ ...validVirement, compte_destination_id: '' }).success).toBe(
      false
    );
    expect(
      saisieSchema.safeParse({ ...validVirement, compte_destination_id: 'caisse' }).success
    ).toBe(false);
  });
});

describe('amountToDecimalString', () => {
  it('normalizes a French comma to a dot and trims', () => {
    expect(amountToDecimalString('150,00')).toBe('150.00');
    expect(amountToDecimalString('  9,5 ')).toBe('9.5');
    expect(amountToDecimalString('42')).toBe('42');
  });
});
