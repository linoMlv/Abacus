import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const listTresorerie = vi.fn();
const definirSoldeInitial = vi.fn();
const creerCompteTresorerie = vi.fn();
const modifierCompteTresorerie = vi.fn();

vi.mock('@/api/accounting', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/accounting')>();
  return {
    ...actual,
    accountingApi: {
      listTresorerie: (...a: unknown[]) => listTresorerie(...a),
      definirSoldeInitial: (...a: unknown[]) => definirSoldeInitial(...a),
      creerCompteTresorerie: (...a: unknown[]) => creerCompteTresorerie(...a),
      modifierCompteTresorerie: (...a: unknown[]) => modifierCompteTresorerie(...a),
    },
  };
});

vi.mock('@/hooks/useActiveAssociation', () => ({
  useActiveAssociation: () => ({ id: 'A', name: 'Asso', role: 'treasurer', status: 'active' }),
}));

import { OnboardingSoldesPage } from '@/pages/OnboardingSoldesPage';

const TRESORERIE = [
  {
    id: 'bq',
    numero: '512',
    libelle: 'Banque',
    type_tresorerie: 'banque',
    iban: null,
    couleur: null,
    ordre: 0,
    is_active: true,
    solde: '0.00',
  },
];

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/asso/A/bienvenue']}>
        <Routes>
          <Route path="/asso/:associationId/bienvenue" element={<OnboardingSoldesPage />} />
          <Route path="/asso/:associationId/synthese" element={<div>Synthèse</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  listTresorerie.mockResolvedValue(TRESORERIE);
  definirSoldeInitial.mockResolvedValue({ ...TRESORERIE[0], solde: '1500.00' });
});

describe('OnboardingSoldesPage', () => {
  it('saves a typed opening balance for the seeded account', async () => {
    renderPage();
    const input = await screen.findByLabelText('Solde de Banque');
    await userEvent.type(input, '1500,00');
    await userEvent.click(screen.getByRole('button', { name: /Enregistrer et continuer/ }));

    await waitFor(() => expect(definirSoldeInitial).toHaveBeenCalledTimes(1));
    const [associationId, compteId, input2] = definirSoldeInitial.mock.calls[0];
    expect(associationId).toBe('A');
    expect(compteId).toBe('bq');
    expect(input2).toMatchObject({ montant: '1500.00' });
  });

  it('skips straight to the dashboard when nothing is entered', async () => {
    renderPage();
    await screen.findByLabelText('Solde de Banque');
    await userEvent.click(screen.getByRole('button', { name: /Enregistrer et continuer/ }));

    expect(await screen.findByText('Synthèse')).toBeInTheDocument();
    expect(definirSoldeInitial).not.toHaveBeenCalled();
  });
});
