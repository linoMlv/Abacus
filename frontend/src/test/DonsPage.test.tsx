import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, expect, it, vi } from 'vitest';

const listDons = vi.fn();
const listRecus = vi.fn();
const creerRecu = vi.fn();
const supprimerRecu = vi.fn();

vi.mock('@/api/dons', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/dons')>();
  return {
    ...actual,
    donsApi: {
      listDons: (...a: unknown[]) => listDons(...a),
      listRecus: (...a: unknown[]) => listRecus(...a),
      creerRecu: (...a: unknown[]) => creerRecu(...a),
      supprimerRecu: (...a: unknown[]) => supprimerRecu(...a),
      recuPdfUrl: () => '/api/asso/A/recus/r1/pdf',
    },
  };
});

import { DonsPage } from '@/pages/DonsPage';

const DONS = [
  {
    ecriture_id: 'e1',
    date: '2026-02-01',
    numero_piece: 3,
    libelle: 'Don Dupont',
    montant: '120.00',
    tiers_id: 't1',
    tiers_nom: 'M. Dupont',
    recu_id: null,
    recu_numero: null,
  },
  {
    ecriture_id: 'e2',
    date: '2026-06-01',
    numero_piece: 7,
    libelle: 'Don Dupont 2',
    montant: '80.00',
    tiers_id: 't1',
    tiers_nom: 'M. Dupont',
    recu_id: null,
    recu_numero: null,
  },
];

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/asso/A/dons']}>
        <Routes>
          <Route path="/asso/:associationId/dons" element={<DonsPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  listDons.mockResolvedValue(DONS);
  listRecus.mockResolvedValue([]);
  creerRecu.mockResolvedValue({ id: 'r1', numero: 1 });
  supprimerRecu.mockResolvedValue(undefined);
});

it('groups pending dons by donor and issues a cumulative receipt', async () => {
  renderPage();
  // One donor group summing the two dons.
  expect(await screen.findByText('M. Dupont')).toBeInTheDocument();
  expect(screen.getByText(/2 dons/)).toBeInTheDocument();

  await userEvent.click(screen.getByRole('button', { name: 'Établir un reçu' }));
  const dialog = await screen.findByRole('dialog');
  // Both dons pre-selected → issue.
  await userEvent.click(within(dialog).getByRole('button', { name: /Établir le reçu/ }));

  await waitFor(() => expect(creerRecu).toHaveBeenCalledTimes(1));
  const [, input] = creerRecu.mock.calls[0];
  expect(input.tiers_id).toBe('t1');
  expect(input.ecriture_ids).toEqual(['e1', 'e2']);
});

it('lists issued receipts and deletes one', async () => {
  listRecus.mockResolvedValue([
    {
      id: 'r1',
      numero: 1,
      tiers_id: 't1',
      tiers_nom: 'M. Dupont',
      date: '2026-04-01',
      annee: 2026,
      montant: '200.00',
      forme: 'numeraire',
      mode_reglement: null,
      annule: false,
    },
  ]);
  renderPage();
  expect(await screen.findByText(/Reçu n° 1 — M\. Dupont/)).toBeInTheDocument();

  await userEvent.click(screen.getByRole('button', { name: /Annuler le reçu/ }));
  await waitFor(() => expect(supprimerRecu).toHaveBeenCalledWith('A', 'r1'));
});
