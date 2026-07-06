import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, expect, it, vi } from 'vitest';

const getBudget = vi.fn();
const saveBudget = vi.fn();
const listExercices = vi.fn();

vi.mock('@/api/budget', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/budget')>();
  return {
    ...actual,
    budgetApi: {
      getBudget: (...a: unknown[]) => getBudget(...a),
      saveBudget: (...a: unknown[]) => saveBudget(...a),
      budgetPdfUrl: () => '/api/asso/A/exports/budget.pdf',
      budgetXlsxUrl: () => '/api/asso/A/exports/budget.xlsx',
    },
  };
});

vi.mock('@/api/accounting', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/accounting')>();
  return {
    ...actual,
    accountingApi: {
      ...actual.accountingApi,
      listExercices: (...a: unknown[]) => listExercices(...a),
    },
  };
});

vi.mock('@/hooks/usePermissions', () => ({
  usePermissions: () => ({ has: () => true }),
}));

import { BudgetPage } from '@/pages/BudgetPage';

const BUDGET = {
  exercice_id: 'ex1',
  exercice_libelle: '2026',
  exercice_statut: 'ouvert' as const,
  lignes: [
    {
      categorie_id: 'c1',
      libelle: 'Cotisations',
      sens: 'recette' as const,
      montant_prevu: '0.00',
      realise: '150.00',
      ecart: '150.00',
    },
    {
      categorie_id: 'c2',
      libelle: 'Locations',
      sens: 'depense' as const,
      montant_prevu: '1000.00',
      realise: '1500.00',
      ecart: '500.00',
    },
  ],
  total_recettes_prevu: '0.00',
  total_recettes_realise: '150.00',
  total_depenses_prevu: '1000.00',
  total_depenses_realise: '1500.00',
  resultat_prevu: '-1000.00',
  resultat_realise: '-1350.00',
};

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/asso/A/budget']}>
        <Routes>
          <Route path="/asso/:associationId/budget" element={<BudgetPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  getBudget.mockResolvedValue(BUDGET);
  saveBudget.mockResolvedValue(BUDGET);
  listExercices.mockResolvedValue([
    {
      id: 'ex1',
      libelle: '2026',
      date_debut: '2026-01-01',
      date_fin: '2026-12-31',
      statut: 'ouvert',
    },
  ]);
});

it('renders the prévu/réalisé grid grouped by recettes and dépenses', async () => {
  renderPage();
  expect(await screen.findByText('Cotisations')).toBeInTheDocument();
  expect(screen.getByText('Locations')).toBeInTheDocument();
  expect(screen.getByText('Recettes')).toBeInTheDocument();
  expect(screen.getByText('Dépenses')).toBeInTheDocument();
  // Réalisé comes from the ledger (validated only).
  expect(screen.getAllByText('150,00 €').length).toBeGreaterThan(0);
});

it('edits a prévu amount and saves the whole grid', async () => {
  renderPage();
  const input = await screen.findByLabelText('Budget prévu pour Cotisations');
  await userEvent.clear(input);
  await userEvent.type(input, '8000');

  const save = screen.getByRole('button', { name: /Enregistrer le budget/ });
  await waitFor(() => expect(save).toBeEnabled());
  await userEvent.click(save);

  await waitFor(() => expect(saveBudget).toHaveBeenCalledTimes(1));
  const [, input_] = saveBudget.mock.calls[0];
  expect(input_.exercice_id).toBe('ex1');
  const byCat = Object.fromEntries(
    input_.lignes.map((l: { categorie_id: string; montant_prevu: string }) => [
      l.categorie_id,
      l.montant_prevu,
    ])
  );
  expect(byCat.c1).toBe('8000');
  expect(byCat.c2).toBe('1000.00'); // untouched line preserved
});
