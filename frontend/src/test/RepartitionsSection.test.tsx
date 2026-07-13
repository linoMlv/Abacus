import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, expect, it, vi } from 'vitest';

const listEcritures = vi.fn();

vi.mock('@/api/accounting', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/accounting')>();
  return {
    ...actual,
    accountingApi: { listEcritures: (...a: unknown[]) => listEcritures(...a) },
  };
});

import { RepartitionsSection } from '@/components/synthese/RepartitionsSection';

const CATEGORIES = [
  { categorie_id: 'c1', libelle: 'Fournitures', sens: 'depense' as const, montant: '300.00' },
  { categorie_id: 'c2', libelle: 'Loyer', sens: 'depense' as const, montant: '100.00' },
  { categorie_id: 'c3', libelle: 'Cotisations', sens: 'recette' as const, montant: '500.00' },
];
const EVENEMENTS = [
  {
    evenement_id: 'ev1',
    nom: 'Gala',
    couleur: null,
    recettes: '200.00',
    depenses: '150.00',
    resultat: '50.00',
  },
];
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
    solde: '1200.00',
  },
];
const REPART_TRESO = [
  { compte_id: 'bq', libelle: 'Compte courant', recettes: '300.00', depenses: '50.00' },
];

function renderSection() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <RepartitionsSection
        associationId="A"
        repartitionCategories={CATEGORIES}
        repartitionEvenements={EVENEMENTS}
        repartitionTresorerie={REPART_TRESO}
        comptes={COMPTES}
        dateFrom="2026-01-01"
        dateTo="2026-12-31"
      />
    </QueryClientProvider>
  );
}

beforeEach(() => {
  listEcritures.mockReset();
  listEcritures.mockResolvedValue([]);
});

it('exposes a tab for each of the three modes', () => {
  renderSection();
  for (const label of ['Catégories', 'Événements', 'Trésorerie']) {
    expect(screen.getByRole('button', { name: label })).toBeInTheDocument();
  }
});

it('shows the dépenses and recettes donuts side by side in the Catégories mode', () => {
  renderSection();
  // Two labelled panels, each with its own legend.
  const depenses = screen.getByRole('group', { name: 'Dépenses' });
  const recettes = screen.getByRole('group', { name: 'Recettes' });
  expect(within(depenses).getByRole('button', { name: /Fournitures/ })).toBeInTheDocument();
  expect(within(depenses).getByRole('button', { name: /Loyer/ })).toBeInTheDocument();
  expect(within(recettes).getByRole('button', { name: /Cotisations/ })).toBeInTheDocument();
});

it('drills into a dépense category with the right server-scoped filter', async () => {
  renderSection();
  const depenses = screen.getByRole('group', { name: 'Dépenses' });
  await userEvent.click(within(depenses).getByRole('button', { name: /Fournitures/ }));
  await waitFor(() =>
    expect(listEcritures).toHaveBeenCalledWith('A', {
      categorie_id: ['c1'],
      date_from: '2026-01-01',
      date_to: '2026-12-31',
    })
  );
});

it('drills into a recette event, narrowing by type_operation', async () => {
  renderSection();
  await userEvent.click(screen.getByRole('button', { name: 'Événements' }));
  const recettes = screen.getByRole('group', { name: 'Recettes' });
  await userEvent.click(within(recettes).getByRole('button', { name: /Gala/ }));
  await waitFor(() =>
    expect(listEcritures).toHaveBeenCalledWith('A', {
      evenement_id: ['ev1'],
      type_operation: ['recette'],
      date_from: '2026-01-01',
      date_to: '2026-12-31',
    })
  );
});

it('drills into a treasury account by solde, without a type filter', async () => {
  renderSection();
  await userEvent.click(screen.getByRole('button', { name: 'Trésorerie' }));
  const solde = screen.getByRole('group', { name: 'Solde' });
  await userEvent.click(within(solde).getByRole('button', { name: /Compte courant/ }));
  await waitFor(() =>
    expect(listEcritures).toHaveBeenCalledWith('A', {
      compte_id: ['bq'],
      date_from: '2026-01-01',
      date_to: '2026-12-31',
    })
  );
});

it('drills into treasury dépenses of an account, narrowing by type_operation', async () => {
  renderSection();
  await userEvent.click(screen.getByRole('button', { name: 'Trésorerie' }));
  const depenses = screen.getByRole('group', { name: 'Dépenses' });
  await userEvent.click(within(depenses).getByRole('button', { name: /Compte courant/ }));
  await waitFor(() =>
    expect(listEcritures).toHaveBeenCalledWith('A', {
      compte_id: ['bq'],
      type_operation: ['depense'],
      date_from: '2026-01-01',
      date_to: '2026-12-31',
    })
  );
});
