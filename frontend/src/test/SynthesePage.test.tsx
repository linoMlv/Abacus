import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const listTresorerie = vi.fn();
const listEvenements = vi.fn();
const creerCompteTresorerie = vi.fn();
const modifierCompteTresorerie = vi.fn();

vi.mock('@/api/accounting', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/accounting')>();
  return {
    ...actual,
    accountingApi: {
      listTresorerie: (...args: unknown[]) => listTresorerie(...args),
      listEvenements: (...args: unknown[]) => listEvenements(...args),
      creerCompteTresorerie: (...args: unknown[]) => creerCompteTresorerie(...args),
      modifierCompteTresorerie: (...args: unknown[]) => modifierCompteTresorerie(...args),
    },
  };
});

vi.mock('@/hooks/useActiveAssociation', () => ({
  useActiveAssociation: () => ({ id: 'A', name: 'Mon Asso', role: 'treasurer', status: 'active' }),
}));

import { SynthesePage } from '@/pages/SynthesePage';

const TRESORERIE = [
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
  {
    id: 'ca',
    numero: '531',
    libelle: 'Caisse buvette',
    type_tresorerie: 'caisse',
    iban: null,
    couleur: null,
    ordre: 1,
    is_active: true,
    solde: '150.00',
  },
];

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/asso/A/synthese']}>
        <Routes>
          <Route path="/asso/:associationId/synthese" element={<SynthesePage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  listTresorerie.mockResolvedValue(TRESORERIE);
  listEvenements.mockResolvedValue([]);
  creerCompteTresorerie.mockResolvedValue({ ...TRESORERIE[0], id: 'new' });
});

describe('SynthesePage', () => {
  it('shows a card per treasury account with its balance', async () => {
    renderPage();
    expect(await screen.findByText('Compte courant')).toBeInTheDocument();
    expect(await screen.findByText('Caisse buvette')).toBeInTheDocument();
    expect(listTresorerie).toHaveBeenCalledWith('A');
  });

  it('shows the consolidated treasury total', async () => {
    renderPage();
    // 500 + 150 = 650 across the accounts.
    expect(await screen.findByText(/650,00/)).toBeInTheDocument();
  });

  it('shows an empty state when there is no treasury account', async () => {
    listTresorerie.mockResolvedValue([]);
    renderPage();
    expect(await screen.findByText(/Aucun compte de trésorerie/)).toBeInTheDocument();
  });

  it('creates a treasury account through the dialog', async () => {
    renderPage();
    await screen.findByText('Compte courant');

    await userEvent.click(screen.getByRole('button', { name: /Nouveau compte/ }));
    const dialog = await screen.findByRole('dialog');
    expect(dialog).toBeInTheDocument();

    await userEvent.type(screen.getByLabelText('Nom'), 'Caisse fête');
    await userEvent.type(screen.getByLabelText(/Solde initial/), '300,00');
    await userEvent.click(screen.getByRole('button', { name: /Créer le compte/ }));

    await waitFor(() => expect(creerCompteTresorerie).toHaveBeenCalledTimes(1));
    const [associationId, input] = creerCompteTresorerie.mock.calls[0];
    expect(associationId).toBe('A');
    expect(input).toMatchObject({ nom: 'Caisse fête', solde_initial: '300.00' });
  });
});
