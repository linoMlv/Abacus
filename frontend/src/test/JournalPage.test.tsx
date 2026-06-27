import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const listEcritures = vi.fn();
const listJournaux = vi.fn();
const listComptes = vi.fn();
const getEcriture = vi.fn();
const validerEcriture = vi.fn();
const supprimerEcriture = vi.fn();

vi.mock('@/api/accounting', () => ({
  accountingApi: {
    listEcritures: (...a: unknown[]) => listEcritures(...a),
    listJournaux: (...a: unknown[]) => listJournaux(...a),
    listComptes: (...a: unknown[]) => listComptes(...a),
    getEcriture: (...a: unknown[]) => getEcriture(...a),
    validerEcriture: (...a: unknown[]) => validerEcriture(...a),
    supprimerEcriture: (...a: unknown[]) => supprimerEcriture(...a),
  },
}));

vi.mock('@/hooks/useActiveAssociation', () => ({
  useActiveAssociation: () => ({ id: 'A', name: 'Asso', role: 'accountant', status: 'active' }),
}));

import { JournalPage } from '@/pages/JournalPage';

const ROWS = [
  {
    id: 'e2',
    exercice_id: 'x',
    journal_id: 'j-ve',
    date: '2026-06-27',
    numero_piece: 2,
    libelle: 'Cotisation Mars',
    statut: 'brouillon',
    origine: 'saisie_simple',
    created_at: '2026-06-27T10:00:00Z',
    validated_at: null,
    montant: '150.00',
    journal_code: 'VE',
  },
  {
    id: 'e1',
    exercice_id: 'x',
    journal_id: 'j-ac',
    date: '2026-06-25',
    numero_piece: 1,
    libelle: 'Loyer',
    statut: 'validee',
    origine: 'manuelle',
    created_at: '2026-06-25T10:00:00Z',
    validated_at: '2026-06-25T11:00:00Z',
    montant: '100.00',
    journal_code: 'AC',
  },
];
const COMPTES = [
  { id: 'c-bq', numero: '512', libelle: 'Banque', classe: 5, type: 'actif', is_active: true },
  {
    id: 'c-co',
    numero: '756',
    libelle: 'Cotisations',
    classe: 7,
    type: 'produit',
    is_active: true,
  },
];
const DETAIL = {
  ...ROWS[0],
  lignes: [
    { id: 'l1', compte_id: 'c-bq', libelle: 'Banque', debit: '150.00', credit: '0' },
    { id: 'l2', compte_id: 'c-co', libelle: 'Cotis', debit: '0', credit: '150.00' },
  ],
};

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/asso/A/journal']}>
        <Routes>
          <Route path="/asso/:associationId/journal" element={<JournalPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  listEcritures.mockResolvedValue(ROWS);
  listJournaux.mockResolvedValue([{ id: 'j-ve', code: 'VE', libelle: 'Ventes' }]);
  listComptes.mockResolvedValue(COMPTES);
  getEcriture.mockResolvedValue(DETAIL);
  validerEcriture.mockResolvedValue({ ...DETAIL, statut: 'validee' });
});

describe('JournalPage', () => {
  it('lists the entries with their journal code', async () => {
    renderPage();
    expect(await screen.findByText('Cotisation Mars')).toBeInTheDocument();
    expect(screen.getByText('Loyer')).toBeInTheDocument();
    expect(screen.getByText('VE')).toBeInTheDocument();
  });

  it('refetches with the statut filter when it changes', async () => {
    renderPage();
    await screen.findByText('Cotisation Mars');

    await userEvent.selectOptions(screen.getByLabelText('Filtrer par statut'), 'brouillon');

    await waitFor(() =>
      expect(listEcritures).toHaveBeenCalledWith(
        'A',
        expect.objectContaining({ statut: 'brouillon' })
      )
    );
  });

  it('opens the detail and validates a draft', async () => {
    renderPage();
    await userEvent.click(await screen.findByText('Cotisation Mars'));

    const dialog = await screen.findByRole('dialog');
    expect(dialog).toBeInTheDocument();
    // Lines render account labels resolved from the chart of accounts.
    expect(await screen.findByText('512 — Banque')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: /Valider/ }));
    await waitFor(() => expect(validerEcriture).toHaveBeenCalledWith('A', 'e2'));
  });
});
