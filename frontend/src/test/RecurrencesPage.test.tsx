import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const listRecurrences = vi.fn();
const genererRecurrences = vi.fn();
const modifierRecurrence = vi.fn();
const supprimerRecurrence = vi.fn();
const listCategories = vi.fn();
const listTresorerie = vi.fn();

vi.mock('@/hooks/usePermissions', () => ({
  usePermissions: () => ({ has: () => true, isLoading: false }),
}));

vi.mock('@/api/accounting', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/accounting')>();
  return {
    ...actual,
    accountingApi: {
      listRecurrences: (...a: unknown[]) => listRecurrences(...a),
      genererRecurrences: (...a: unknown[]) => genererRecurrences(...a),
      modifierRecurrence: (...a: unknown[]) => modifierRecurrence(...a),
      supprimerRecurrence: (...a: unknown[]) => supprimerRecurrence(...a),
      listCategories: (...a: unknown[]) => listCategories(...a),
      listTresorerie: (...a: unknown[]) => listTresorerie(...a),
    },
  };
});

import { RecurrencesPage } from '@/pages/RecurrencesPage';

const REC = {
  id: 'r1',
  libelle: 'Loyer du local',
  categorie_id: 'c1',
  compte_tresorerie_id: 'bq',
  montant: '500.00',
  tiers_id: null,
  evenement_id: null,
  reference_externe: null,
  mode_reglement: null,
  periodicite: 'mensuelle',
  prochaine_echeance: '2026-08-01',
  date_fin: null,
  mode: 'proposition',
  actif: true,
};

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/asso/A/recurrences']}>
        <Routes>
          <Route path="/asso/:associationId/recurrences" element={<RecurrencesPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  listRecurrences.mockResolvedValue([REC]);
  genererRecurrences.mockResolvedValue({ generees: 2 });
  modifierRecurrence.mockResolvedValue({ ...REC, actif: false });
  supprimerRecurrence.mockResolvedValue(undefined);
  listCategories.mockResolvedValue([]);
  listTresorerie.mockResolvedValue([]);
});

describe('RecurrencesPage', () => {
  it('lists the recurrences', async () => {
    renderPage();
    expect(await screen.findByText('Loyer du local')).toBeInTheDocument();
    expect(screen.getByText(/Mensuelle/)).toBeInTheDocument();
  });

  it('generates due entries and reports the count', async () => {
    renderPage();
    await screen.findByText('Loyer du local');
    await userEvent.click(screen.getByRole('button', { name: /Générer les échéances dues/ }));
    await waitFor(() => expect(genererRecurrences).toHaveBeenCalledWith('A'));
    expect(await screen.findByText(/2 écriture\(s\) générée\(s\)/)).toBeInTheDocument();
  });

  it('pauses a recurrence', async () => {
    renderPage();
    await screen.findByText('Loyer du local');
    await userEvent.click(screen.getByRole('button', { name: 'Mettre en pause' }));
    await waitFor(() =>
      expect(modifierRecurrence).toHaveBeenCalledWith('A', 'r1', { actif: false })
    );
  });

  it('deletes a recurrence after confirmation', async () => {
    renderPage();
    await screen.findByText('Loyer du local');
    await userEvent.click(screen.getByRole('button', { name: 'Supprimer' }));
    await userEvent.click(screen.getByRole('button', { name: 'Confirmer' }));
    await waitFor(() => expect(supprimerRecurrence).toHaveBeenCalledWith('A', 'r1'));
  });
});
