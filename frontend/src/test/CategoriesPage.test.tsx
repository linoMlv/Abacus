import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const listCategories = vi.fn();
const modifierCategorie = vi.fn();
const creerCategorie = vi.fn();

vi.mock('@/api/accounting', () => ({
  accountingApi: {
    listCategories: (...a: unknown[]) => listCategories(...a),
    modifierCategorie: (...a: unknown[]) => modifierCategorie(...a),
    creerCategorie: (...a: unknown[]) => creerCategorie(...a),
  },
}));

vi.mock('@/hooks/usePermissions', () => ({
  usePermissions: () => ({ has: () => true, isLoading: false }),
}));

vi.mock('@/hooks/useActiveAssociation', () => ({
  useActiveAssociation: () => ({ id: 'A', name: 'Asso', role: 'treasurer', status: 'active' }),
}));

import { CategoriesPage } from '@/pages/CategoriesPage';

const cat = (over: Partial<Record<string, unknown>>) => ({
  id: 'x',
  sens: 'recette',
  libelle: 'Cat',
  compte_id: 'c',
  journal_id: 'j',
  is_active: true,
  ordre: 0,
  ...over,
});

const CATEGORIES = [
  cat({ id: 'r1', libelle: 'Cotisations', ordre: 0 }),
  cat({ id: 'r2', libelle: 'Dons', ordre: 1 }),
  cat({ id: 'd1', sens: 'depense', libelle: 'Loyer', ordre: 2 }),
];

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/asso/A/categories']}>
        <Routes>
          <Route path="/asso/:associationId/categories" element={<CategoriesPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  listCategories.mockResolvedValue(CATEGORIES);
  modifierCategorie.mockResolvedValue(cat({}));
});

describe('CategoriesPage', () => {
  it('lists categories under their sens section', async () => {
    renderPage();
    expect(await screen.findByText('Cotisations')).toBeInTheDocument();
    expect(screen.getByText('Loyer')).toBeInTheDocument();
    expect(listCategories).toHaveBeenCalledWith('A', undefined, true);
  });

  it('archives a category', async () => {
    renderPage();
    await screen.findByText('Cotisations');
    // First recette row's archive button.
    await userEvent.click(screen.getAllByRole('button', { name: 'Archiver' })[0]);
    await waitFor(() =>
      expect(modifierCategorie).toHaveBeenCalledWith('A', 'r1', { is_active: false })
    );
  });

  it('reorders a category by swapping ordre with its neighbour', async () => {
    renderPage();
    await screen.findByText('Cotisations');
    // Move the first recette ("Cotisations", ordre 0) down, swapping with "Dons".
    await userEvent.click(screen.getAllByRole('button', { name: 'Descendre' })[0]);
    await waitFor(() => expect(modifierCategorie).toHaveBeenCalledWith('A', 'r1', { ordre: 1 }));
    expect(modifierCategorie).toHaveBeenCalledWith('A', 'r2', { ordre: 0 });
  });
});
