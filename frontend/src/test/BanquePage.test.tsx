import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const listTresorerie = vi.fn();
const listLignesBancaires = vi.fn();
const ignorerLigne = vi.fn();
const delettrerLigne = vi.fn();
const suggestionsRapprochement = vi.fn();
const listCategories = vi.fn();

vi.mock('@/hooks/usePermissions', () => ({
  usePermissions: () => ({ has: () => true, isLoading: false }),
}));

vi.mock('@/api/accounting', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/accounting')>();
  return {
    ...actual,
    accountingApi: {
      listTresorerie: (...a: unknown[]) => listTresorerie(...a),
      listLignesBancaires: (...a: unknown[]) => listLignesBancaires(...a),
      ignorerLigne: (...a: unknown[]) => ignorerLigne(...a),
      delettrerLigne: (...a: unknown[]) => delettrerLigne(...a),
      suggestionsRapprochement: (...a: unknown[]) => suggestionsRapprochement(...a),
      listCategories: (...a: unknown[]) => listCategories(...a),
    },
  };
});

import { BanquePage } from '@/pages/BanquePage';

const LIGNES = [
  {
    id: 'l1',
    import_id: 'i1',
    compte_id: 'bq',
    date_operation: '2026-06-15',
    libelle: 'Cotisation Dupont',
    montant: '150.00',
    statut: 'non_rapproche',
    ecriture_id: null,
  },
  {
    id: 'l2',
    import_id: 'i1',
    compte_id: 'bq',
    date_operation: '2026-06-18',
    libelle: 'Loyer',
    montant: '-500.00',
    statut: 'rapproche',
    ecriture_id: 'e9',
  },
];

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/asso/A/banque']}>
        <Routes>
          <Route path="/asso/:associationId/banque" element={<BanquePage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  listTresorerie.mockResolvedValue([
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
  ]);
  listLignesBancaires.mockImplementation((_assoc: string, params: { statut?: string } = {}) =>
    Promise.resolve(params.statut ? LIGNES.filter((l) => l.statut === params.statut) : LIGNES)
  );
  ignorerLigne.mockResolvedValue({ ...LIGNES[0], statut: 'ignore' });
  delettrerLigne.mockResolvedValue({ ...LIGNES[1], statut: 'non_rapproche', ecriture_id: null });
  suggestionsRapprochement.mockResolvedValue([]);
  listCategories.mockResolvedValue([]);
});

describe('BanquePage', () => {
  it('lists the statement lines to reconcile', async () => {
    renderPage();
    expect(await screen.findByText('Cotisation Dupont')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Rapprocher' })).toBeInTheDocument();
  });

  it('sets a line aside (ignore)', async () => {
    renderPage();
    await screen.findByText('Cotisation Dupont');
    await userEvent.click(screen.getByRole('button', { name: 'Ignorer' }));
    await waitFor(() => expect(ignorerLigne).toHaveBeenCalledWith('A', 'l1', true));
  });

  it('undoes a lettrage from the "Rapprochées" tab', async () => {
    renderPage();
    await screen.findByText('Cotisation Dupont');
    await userEvent.click(screen.getByRole('button', { name: 'Rapprochées' }));
    await userEvent.click(await screen.findByRole('button', { name: 'Délettrer' }));
    await waitFor(() => expect(delettrerLigne).toHaveBeenCalledWith('A', 'l2'));
  });

  it('opens the reconcile dialog for a line', async () => {
    renderPage();
    await screen.findByText('Cotisation Dupont');
    await userEvent.click(screen.getByRole('button', { name: 'Rapprocher' }));
    expect(await screen.findByText('Rapprocher l’opération')).toBeInTheDocument();
    await waitFor(() => expect(suggestionsRapprochement).toHaveBeenCalledWith('A', 'l1'));
  });
});
