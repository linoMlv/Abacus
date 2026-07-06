import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const listTresorerie = vi.fn();
const listEvenements = vi.fn();
const getSynthese = vi.fn();
const creerCompteTresorerie = vi.fn();
const modifierCompteTresorerie = vi.fn();

vi.mock('@/api/accounting', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/accounting')>();
  return {
    ...actual,
    accountingApi: {
      listTresorerie: (...args: unknown[]) => listTresorerie(...args),
      listEvenements: (...args: unknown[]) => listEvenements(...args),
      getSynthese: (...args: unknown[]) => getSynthese(...args),
      creerCompteTresorerie: (...args: unknown[]) => creerCompteTresorerie(...args),
      modifierCompteTresorerie: (...args: unknown[]) => modifierCompteTresorerie(...args),
      relevePdfUrl: (assoc: string, compteId: string) =>
        `/api/asso/${assoc}/exports/tresorerie/${compteId}/releve.pdf`,
      compteResultatPdfUrl: (assoc: string) => `/api/asso/${assoc}/exports/compte-resultat.pdf`,
      bilanPdfUrl: (assoc: string) => `/api/asso/${assoc}/exports/bilan.pdf`,
    },
  };
});

const EMPTY_SYNTHESE = {
  date_from: '2026-01-01',
  date_to: '2026-12-31',
  resultat: { recettes: '0.00', depenses: '0.00', resultat: '0.00' },
  repartition_categories: [],
  repartition_evenements: [],
  courbe_tresorerie: [],
  alertes: {
    brouillons: 0,
    evenements_depasses: [],
    exercices_a_cloturer: [],
    budgets_depasses: [],
  },
  budget: null,
};

vi.mock('@/hooks/usePermissions', () => ({
  usePermissions: () => ({ has: () => true, isLoading: false }),
}));

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
  localStorage.clear();
  listTresorerie.mockResolvedValue(TRESORERIE);
  listEvenements.mockResolvedValue([]);
  getSynthese.mockResolvedValue(EMPTY_SYNTHESE);
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

  it('fills the result / recettes / dépenses tiles from the synthesis', async () => {
    getSynthese.mockResolvedValue({
      ...EMPTY_SYNTHESE,
      resultat: { recettes: '300.00', depenses: '75.00', resultat: '225.00' },
    });
    renderPage();
    expect(await screen.findByText(/300,00/)).toBeInTheDocument();
    expect(await screen.findByText(/225,00/)).toBeInTheDocument();
    expect(await screen.findByText(/75,00/)).toBeInTheDocument();
  });

  it('surfaces alerts (drafts, over-budget event, fiscal year due)', async () => {
    getSynthese.mockResolvedValue({
      ...EMPTY_SYNTHESE,
      alertes: {
        brouillons: 3,
        evenements_depasses: [
          {
            evenement_id: 'ev1',
            nom: 'Gala',
            budget_depenses: '10.00',
            realise_depenses: '50.00',
          },
        ],
        exercices_a_cloturer: [{ exercice_id: 'ex1', libelle: '2025', date_fin: '2025-12-31' }],
        budgets_depasses: [
          { categorie_id: 'c1', libelle: 'Locations', montant_prevu: '100.00', realise: '150.00' },
        ],
      },
    });
    renderPage();
    expect(await screen.findByText(/3 écritures en brouillon à valider/)).toBeInTheDocument();
    expect(await screen.findByText(/« Gala » dépasse son budget/)).toBeInTheDocument();
    expect(await screen.findByText(/Exercice « 2025 » échu/)).toBeInTheDocument();
    expect(await screen.findByText(/« Locations » dépasse son budget/)).toBeInTheDocument();
  });

  it('shows the budget widget when a budget is set', async () => {
    getSynthese.mockResolvedValue({
      ...EMPTY_SYNTHESE,
      budget: {
        exercice_id: 'ex1',
        exercice_libelle: '2026',
        recettes_prevu: '5000.00',
        recettes_realise: '3000.00',
        depenses_prevu: '1000.00',
        depenses_realise: '1500.00',
        resultat_prevu: '4000.00',
        resultat_realise: '1500.00',
        depassements: [
          {
            categorie_id: 'c1',
            libelle: 'Locations',
            montant_prevu: '1000.00',
            realise: '1500.00',
          },
        ],
      },
    });
    renderPage();
    expect(await screen.findByText('Budget 2026')).toBeInTheDocument();
    expect(await screen.findByText(/1 poste en dépassement/)).toBeInTheDocument();
  });

  it('dismisses an alert so it no longer shows', async () => {
    getSynthese.mockResolvedValue({
      ...EMPTY_SYNTHESE,
      alertes: {
        brouillons: 3,
        evenements_depasses: [],
        exercices_a_cloturer: [],
        budgets_depasses: [],
      },
    });
    renderPage();
    expect(await screen.findByText(/3 écritures en brouillon à valider/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: /Masquer cette alerte/ }));

    await waitFor(() =>
      expect(screen.queryByText(/3 écritures en brouillon à valider/)).not.toBeInTheDocument()
    );
  });

  it('refetches with an explicit period when a preset is chosen', async () => {
    renderPage();
    await screen.findByText('Compte courant');
    // Default preset is "Exercice": no dates sent (server uses the open exercice).
    await waitFor(() => expect(getSynthese).toHaveBeenCalledWith('A', {}));

    await userEvent.click(screen.getByRole('button', { name: 'Mois' }));
    await waitFor(() =>
      expect(getSynthese).toHaveBeenCalledWith(
        'A',
        expect.objectContaining({
          date_from: expect.stringMatching(/^\d{4}-\d{2}-01$/),
          date_to: expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/),
        })
      )
    );
  });
});
