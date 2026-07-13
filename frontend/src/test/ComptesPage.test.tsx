import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const listPlanComptable = vi.fn();
const getBalance = vi.fn();
const getGrandLivre = vi.fn();
const getRapprochement = vi.fn();
const creerCompte = vi.fn();
const modifierCompte = vi.fn();
const listExercices = vi.fn();

vi.mock('@/api/accounting', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/accounting')>();
  return {
    ...actual,
    accountingApi: {
      listPlanComptable: (...a: unknown[]) => listPlanComptable(...a),
      getBalance: (...a: unknown[]) => getBalance(...a),
      getGrandLivre: (...a: unknown[]) => getGrandLivre(...a),
      getRapprochement: (...a: unknown[]) => getRapprochement(...a),
      creerCompte: (...a: unknown[]) => creerCompte(...a),
      modifierCompte: (...a: unknown[]) => modifierCompte(...a),
      listExercices: (...a: unknown[]) => listExercices(...a),
    },
  };
});

const has = vi.fn();
vi.mock('@/hooks/usePermissions', () => ({
  usePermissions: () => ({ has: (p: string) => has(p), isLoading: false }),
}));

import { ComptesPage } from '@/pages/ComptesPage';

const COMPTES = [
  { id: 'c-bq', numero: '512', libelle: 'Banque', classe: 5, type: 'actif', is_active: true },
  { id: 'c-606', numero: '606', libelle: 'Achats', classe: 6, type: 'charge', is_active: true },
  {
    id: 'c-6064',
    numero: '6064',
    libelle: 'Fournitures',
    classe: 6,
    type: 'charge',
    is_active: true,
  },
  {
    id: 'c-756',
    numero: '756',
    libelle: 'Cotisations',
    classe: 7,
    type: 'produit',
    is_active: true,
  },
];

const BALANCE = [
  {
    compte_id: 'c-6064',
    numero: '6064',
    libelle: 'Fournitures',
    total_debit: '80.00',
    total_credit: '0.00',
    solde: '80.00',
  },
  {
    compte_id: 'c-756',
    numero: '756',
    libelle: 'Cotisations',
    total_debit: '0.00',
    total_credit: '80.00',
    solde: '-80.00',
  },
];

const RAPPROCHEMENT = [
  {
    compte_id: 'c-bq',
    numero: '512',
    libelle: 'Compte courant',
    solde_comptable: '100.00',
    nb_non_rapprochees: 2,
    montant_non_rapproche: '42.00',
    solde_bancaire_estime: '142.00',
    dernier_import: '2026-07-01T09:00:00Z',
  },
];

function renderPage(tab?: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const path = `/asso/A/comptes${tab ? `?tab=${tab}` : ''}`;
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/asso/:associationId/comptes" element={<ComptesPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  has.mockReturnValue(true);
  listPlanComptable.mockResolvedValue(COMPTES);
  getBalance.mockResolvedValue(BALANCE);
  getGrandLivre.mockResolvedValue([
    {
      ecriture_id: 'e1',
      date: '2026-06-25',
      numero_piece: 1,
      journal_id: 'j-ac',
      libelle: 'Ramette papier',
      debit: '80.00',
      credit: '0.00',
      solde: '80.00',
    },
  ]);
  getRapprochement.mockResolvedValue(RAPPROCHEMENT);
  listExercices.mockResolvedValue([
    {
      id: 'x1',
      libelle: '2026',
      date_debut: '2026-01-01',
      date_fin: '2026-12-31',
      statut: 'ouvert',
      report_a_nouveau_genere: false,
    },
  ]);
});

describe('Plan comptable', () => {
  it('groups accounts under their plain-language family', async () => {
    renderPage();

    expect(await screen.findByText('Fournitures')).toBeInTheDocument();
    expect(screen.getByText('Dépenses')).toBeInTheDocument();
    expect(screen.getByText('Recettes')).toBeInTheDocument();
  });

  it('creates an account under the chosen rubrique, letting the server number it', async () => {
    const user = userEvent.setup();
    creerCompte.mockResolvedValue({ ...COMPTES[2], id: 'new', numero: '6061' });
    renderPage();
    await screen.findByText('Fournitures');

    // The "Dépenses" family sits third in the plan; use its own Add button.
    const depenses = screen.getByRole('heading', { name: 'Dépenses' }).closest('section')!;
    await user.click(within(depenses).getByRole('button', { name: /ajouter/i }));

    await user.selectOptions(await screen.findByLabelText('Rubrique'), '606');
    await user.type(screen.getByLabelText('Libellé'), 'Petit équipement');
    await user.click(screen.getByRole('button', { name: /créer le compte/i }));

    await waitFor(() =>
      expect(creerCompte).toHaveBeenCalledWith('A', {
        libelle: 'Petit équipement',
        type: 'charge',
        prefixe: '606',
      })
    );
  });

  it('hides the edition affordances without the account permission', async () => {
    has.mockImplementation((p: string) => p !== 'account:manage');
    renderPage();
    await screen.findByText('Fournitures');

    expect(screen.queryByRole('button', { name: /ajouter/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /archiver/i })).not.toBeInTheDocument();
  });

  it('archives an account through the API', async () => {
    const user = userEvent.setup();
    modifierCompte.mockResolvedValue({ ...COMPTES[2], is_active: false });
    renderPage();
    await screen.findByText('Fournitures');

    const rows = screen.getAllByRole('button', { name: 'Archiver' });
    await user.click(rows[0]);

    await waitFor(() =>
      expect(modifierCompte).toHaveBeenCalledWith('A', expect.any(String), { is_active: false })
    );
  });
});

describe('Balance', () => {
  it('totals debit and credit and states the balance is equilibrée', async () => {
    renderPage('balance');

    expect(await screen.findByText('Totaux')).toBeInTheDocument();
    expect(screen.getByText('Équilibrée')).toBeInTheDocument();
  });
});

describe('Grand livre', () => {
  it('shows the ledger of the first moved account with its running balance', async () => {
    renderPage('grand-livre');

    expect(await screen.findByText('Ramette papier')).toBeInTheDocument();
    await waitFor(() => expect(getGrandLivre).toHaveBeenCalledWith('A', 'c-6064', undefined));
  });
});

describe('Rapprochement', () => {
  it('states the gap between the books and the bank', async () => {
    renderPage('rapprochement');

    expect(await screen.findByText('Compte courant')).toBeInTheDocument();
    expect(screen.getByText('2 à rapprocher')).toBeInTheDocument();
    expect(screen.getByText('142,00 €')).toBeInTheDocument(); // solde attendu en banque
  });
});
