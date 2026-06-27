import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const listCategories = vi.fn();
const listComptes = vi.fn();
const creerSaisieSimple = vi.fn();

vi.mock('@/api/accounting', () => ({
  CLASSE_TRESORERIE: 5,
  accountingApi: {
    listCategories: (...args: unknown[]) => listCategories(...args),
    listComptes: (...args: unknown[]) => listComptes(...args),
    creerSaisieSimple: (...args: unknown[]) => creerSaisieSimple(...args),
  },
}));

vi.mock('@/hooks/useActiveAssociation', () => ({
  useActiveAssociation: () => ({ id: 'A', name: 'Asso', role: 'treasurer', status: 'active' }),
}));

// Imported after the mocks so the page picks them up.
import { SaisiePage } from '@/pages/SaisiePage';

const CATEGORIES = [
  {
    id: 'cat-rec',
    sens: 'recette',
    libelle: 'Cotisations',
    compte_id: 'c1',
    journal_id: 'j1',
    is_active: true,
    ordre: 0,
  },
  {
    id: 'cat-dep',
    sens: 'depense',
    libelle: 'Achats',
    compte_id: 'c2',
    journal_id: 'j2',
    is_active: true,
    ordre: 1,
  },
];
const COMPTES = [
  { id: 'bq', numero: '512', libelle: 'Banque', classe: 5, type: 'actif', is_active: true },
  { id: 'ca', numero: '531', libelle: 'Caisse', classe: 5, type: 'actif', is_active: true },
];

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/asso/A/saisie']}>
        <Routes>
          <Route path="/asso/:associationId/saisie" element={<SaisiePage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  listCategories.mockResolvedValue(CATEGORIES);
  listComptes.mockResolvedValue(COMPTES);
  creerSaisieSimple.mockResolvedValue({ numero_piece: 7 });
});

describe('SaisiePage', () => {
  it('shows the recette categories and treasury accounts once loaded', async () => {
    renderPage();
    expect(await screen.findByRole('option', { name: 'Cotisations' })).toBeInTheDocument();
    expect(await screen.findByRole('option', { name: '512 — Banque' })).toBeInTheDocument();
    // The depense-only category is filtered out of the default (recette) view.
    expect(screen.queryByRole('option', { name: 'Achats' })).not.toBeInTheDocument();
  });

  it('blocks submission and shows an error when the amount is empty', async () => {
    renderPage();
    await screen.findByRole('option', { name: 'Cotisations' });

    await userEvent.click(screen.getByRole('button', { name: /Enregistrer/ }));

    expect(await screen.findByText('Indiquez un montant.')).toBeInTheDocument();
    expect(creerSaisieSimple).not.toHaveBeenCalled();
  });

  it('posts a normalized entry and confirms success on a valid submit', async () => {
    renderPage();
    await screen.findByRole('option', { name: 'Cotisations' });
    await screen.findByRole('option', { name: '512 — Banque' });

    await userEvent.type(screen.getByLabelText('Montant (€)'), '150,00');
    await userEvent.click(screen.getByRole('button', { name: /Enregistrer/ }));

    await waitFor(() => expect(creerSaisieSimple).toHaveBeenCalledTimes(1));
    const [associationId, input] = creerSaisieSimple.mock.calls[0];
    expect(associationId).toBe('A');
    expect(input).toMatchObject({
      categorie_id: 'cat-rec',
      compte_tresorerie_id: 'bq',
      montant: '150.00',
    });
    expect(input.libelle).toBeUndefined();
    expect(await screen.findByText(/Écriture n° 7 enregistrée/)).toBeInTheDocument();
  });
});
