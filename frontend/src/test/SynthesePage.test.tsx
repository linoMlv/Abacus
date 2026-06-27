import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const listTresorerie = vi.fn();

vi.mock('@/api/accounting', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/accounting')>();
  return {
    ...actual,
    accountingApi: { listTresorerie: (...args: unknown[]) => listTresorerie(...args) },
  };
});

vi.mock('@/hooks/useActiveAssociation', () => ({
  useActiveAssociation: () => ({ id: 'A', name: 'Mon Asso', role: 'treasurer', status: 'active' }),
}));

import { SynthesePage } from '@/pages/SynthesePage';

const TRESORERIE = [
  {
    id: 'bq',
    numero: '512',
    libelle: 'Compte courant',
    type_tresorerie: 'banque',
    iban: null,
    couleur: null,
    ordre: 0,
    is_active: true,
    solde: '500.00',
  },
  {
    id: 'ca',
    numero: '531',
    libelle: 'Caisse buvette',
    type_tresorerie: 'caisse',
    iban: null,
    couleur: null,
    ordre: 1,
    is_active: true,
    solde: '150.00',
  },
];

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/asso/A/synthese']}>
        <Routes>
          <Route path="/asso/:associationId/synthese" element={<SynthesePage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  listTresorerie.mockResolvedValue(TRESORERIE);
});

describe('SynthesePage', () => {
  it('shows a card per treasury account with its balance', async () => {
    renderPage();
    expect(await screen.findByText('Compte courant')).toBeInTheDocument();
    expect(await screen.findByText('Caisse buvette')).toBeInTheDocument();
    expect(listTresorerie).toHaveBeenCalledWith('A');
  });

  it('shows the consolidated treasury total', async () => {
    renderPage();
    // 500 + 150 = 650 across the accounts.
    expect(await screen.findByText(/650,00/)).toBeInTheDocument();
  });

  it('shows an empty state when there is no treasury account', async () => {
    listTresorerie.mockResolvedValue([]);
    renderPage();
    expect(await screen.findByText('Aucun compte de trésorerie.')).toBeInTheDocument();
  });
});
