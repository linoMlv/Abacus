import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const listEvenements = vi.fn();
const listEcritures = vi.fn();
const creerEvenement = vi.fn();

vi.mock('@/api/accounting', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/accounting')>();
  return {
    ...actual,
    accountingApi: {
      listEvenements: (...a: unknown[]) => listEvenements(...a),
      listEcritures: (...a: unknown[]) => listEcritures(...a),
      creerEvenement: (...a: unknown[]) => creerEvenement(...a),
      evenementBilanPdfUrl: (assoc: string, id: string) =>
        `/api/asso/${assoc}/exports/evenements/${id}/bilan.pdf`,
    },
  };
});

vi.mock('@/hooks/usePermissions', () => ({
  usePermissions: () => ({ has: () => true, isLoading: false }),
}));

vi.mock('@/hooks/useActiveAssociation', () => ({
  useActiveAssociation: () => ({ id: 'A', name: 'Asso', role: 'treasurer', status: 'active' }),
}));

import { EvenementsPanel } from '@/components/saisie/EvenementsPanel';

const GALA = {
  id: 'ev1',
  nom: 'Gala 2026',
  description: 'Soirée annuelle',
  date_debut: '2026-09-01',
  date_fin: null,
  budget_recettes: '2000.00',
  budget_depenses: '800.00',
  statut: 'actif',
  couleur: '#7C3AED',
  realise_recettes: '1500.00',
  realise_depenses: '600.00',
  resultat: '900.00',
};

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/asso/A/saisie']}>
        <Routes>
          <Route path="/asso/:associationId/saisie" element={<EvenementsPanel />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  listEvenements.mockResolvedValue([GALA]);
  listEcritures.mockResolvedValue([
    {
      id: 'e1',
      exercice_id: 'x',
      journal_id: 'j',
      date: '2026-09-02',
      numero_piece: 4,
      libelle: 'Billetterie',
      statut: 'brouillon',
      origine: 'saisie_simple',
      created_at: '2026-09-02T10:00:00Z',
      validated_at: null,
      montant: '1500.00',
      journal_code: 'VE',
    },
  ]);
  creerEvenement.mockResolvedValue({ ...GALA, id: 'ev-new', nom: 'Sortie' });
});

describe('EvenementsPage', () => {
  it('lists events with their result', async () => {
    renderPage();
    expect(await screen.findByText('Gala 2026')).toBeInTheDocument();
    expect(screen.getByText('900,00 €')).toBeInTheDocument();
  });

  it('shows an empty state when there is no event', async () => {
    listEvenements.mockResolvedValue([]);
    renderPage();
    expect(await screen.findByText(/Aucun événement/)).toBeInTheDocument();
  });

  it('opens an event and lists its operations', async () => {
    renderPage();
    await userEvent.click(await screen.findByRole('button', { name: /Ouvrir Gala 2026/ }));

    expect(await screen.findByText('Billetterie')).toBeInTheDocument();
    await waitFor(() => expect(listEcritures).toHaveBeenCalledWith('A', { evenement_id: ['ev1'] }));
  });

  it('opens the create dialog', async () => {
    renderPage();
    await screen.findByText('Gala 2026');
    await userEvent.click(screen.getByRole('button', { name: /Nouvel événement/ }));
    expect(await screen.findByRole('dialog')).toBeInTheDocument();
  });
});
