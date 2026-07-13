import { render, screen } from '@testing-library/react';
import { expect, it } from 'vitest';

import { ResultStrip } from '@/components/synthese/ResultStrip';
import { SyntheseHero } from '@/components/synthese/SyntheseHero';

/** Matches an element whose own text equals `s` once every kind of space is stripped.
 * `\s` covers the regular, no-break and narrow-no-break spaces Intl may emit. */
function money(s: string) {
  return (_: string, el: Element | null) => el?.textContent?.replace(/\s/g, '') === s;
}

const COMPTES = [
  {
    id: 'bq',
    numero: '512',
    libelle: 'Compte courant',
    type_tresorerie: 'banque' as const,
    iban: null,
    couleur: null,
    ordre: 0,
    is_active: true,
    solde: '9200.00',
  },
  {
    id: 'ca',
    numero: '531',
    libelle: 'Caisse',
    type_tresorerie: 'caisse' as const,
    iban: null,
    couleur: null,
    ordre: 1,
    is_active: true,
    solde: '480.00',
  },
];

it('shows the consolidated total, the period delta and one chip per account', () => {
  render(
    <SyntheseHero
      total={9680}
      comptes={COMPTES}
      courbe={[
        { date: '2026-01-01', solde: '8440.00' },
        { date: '2026-06-30', solde: '9680.00' },
      ]}
    />
  );
  expect(screen.getByText(/trésorerie consolidée/i)).toBeInTheDocument();
  expect(screen.getByText(money('9680,00€'))).toBeInTheDocument();
  // delta = 9680 − 8440 = +1240 over the period
  expect(screen.getByText(money('+1240,00€'))).toBeInTheDocument();
  expect(screen.getByText('Compte courant')).toBeInTheDocument();
  expect(screen.getByText('Caisse')).toBeInTheDocument();
});

it('renders the recettes − dépenses = résultat equation', () => {
  render(
    <ResultStrip resultat={{ recettes: '5400.00', depenses: '4160.00', resultat: '1240.00' }} />
  );
  expect(screen.getByText('Recettes')).toBeInTheDocument();
  expect(screen.getByText('Dépenses')).toBeInTheDocument();
  expect(screen.getByText('Résultat')).toBeInTheDocument();
  expect(screen.getByText(money('5400,00€'))).toBeInTheDocument();
  expect(screen.getByText(money('4160,00€'))).toBeInTheDocument();
  expect(screen.getByText(money('1240,00€'))).toBeInTheDocument();
});
