import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const listTresorerie = vi.fn();
const listEvenements = vi.fn();
const triggerDownload = vi.fn();

vi.mock('@/lib/download', () => ({
  triggerDownload: (...a: unknown[]) => triggerDownload(...a),
}));

vi.mock('@/api/accounting', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/accounting')>();
  return {
    ...actual,
    accountingApi: {
      listTresorerie: (...a: unknown[]) => listTresorerie(...a),
      listEvenements: (...a: unknown[]) => listEvenements(...a),
      journalPdfUrl: (assoc: string) => `/api/asso/${assoc}/exports/journal.pdf`,
      journalXlsxUrl: (assoc: string) => `/api/asso/${assoc}/exports/journal.xlsx`,
      grandLivrePdfUrl: (assoc: string) => `/api/asso/${assoc}/exports/grand-livre.pdf`,
      grandLivreXlsxUrl: (assoc: string) => `/api/asso/${assoc}/exports/grand-livre.xlsx`,
      compteResultatPdfUrl: (assoc: string) => `/api/asso/${assoc}/exports/compte-resultat.pdf`,
      bilanPdfUrl: (assoc: string) => `/api/asso/${assoc}/exports/bilan.pdf`,
      relevePdfUrl: (assoc: string, compteId: string) =>
        `/api/asso/${assoc}/exports/tresorerie/${compteId}/releve.pdf`,
      evenementBilanPdfUrl: (assoc: string, eventId: string) =>
        `/api/asso/${assoc}/exports/evenements/${eventId}/bilan.pdf`,
    },
  };
});

import { RapportsPage } from '@/pages/RapportsPage';

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/asso/A/rapports']}>
        <Routes>
          <Route path="/asso/:associationId/rapports" element={<RapportsPage />} />
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
  listEvenements.mockResolvedValue([{ id: 'ev1', nom: 'Gala', statut: 'actif', couleur: null }]);
});

describe('RapportsPage', () => {
  it('downloads the journal PDF', async () => {
    renderPage();
    await userEvent.click(await screen.findByRole('button', { name: /Journal \(PDF\)/ }));
    expect(triggerDownload).toHaveBeenCalledWith('/api/asso/A/exports/journal.pdf');
  });

  it('lists a treasury statement and an event balance sheet', async () => {
    renderPage();
    expect(await screen.findByRole('button', { name: /Compte courant/ })).toBeInTheDocument();
    const eventBtn = await screen.findByRole('button', { name: /Bilan « Gala »/ });
    await userEvent.click(eventBtn);
    await waitFor(() =>
      expect(triggerDownload).toHaveBeenCalledWith('/api/asso/A/exports/evenements/ev1/bilan.pdf')
    );
  });
});
