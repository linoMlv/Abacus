import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const listCategories = vi.fn();
const listTresorerie = vi.fn();
const listTiers = vi.fn();
const creerSaisieSimple = vi.fn();
const creerVirement = vi.fn();
const creerCategorie = vi.fn();
const modifierCategorie = vi.fn();
const creerTiers = vi.fn();
const listEvenements = vi.fn();
const creerEvenement = vi.fn();
const uploadJustificatif = vi.fn();

vi.mock('@/api/accounting', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/accounting')>();
  return {
    ...actual,
    accountingApi: {
      listCategories: (...args: unknown[]) => listCategories(...args),
      listTresorerie: (...args: unknown[]) => listTresorerie(...args),
      listTiers: (...args: unknown[]) => listTiers(...args),
      listEvenements: (...args: unknown[]) => listEvenements(...args),
      creerSaisieSimple: (...args: unknown[]) => creerSaisieSimple(...args),
      creerVirement: (...args: unknown[]) => creerVirement(...args),
      creerCategorie: (...args: unknown[]) => creerCategorie(...args),
      modifierCategorie: (...args: unknown[]) => modifierCategorie(...args),
      creerTiers: (...args: unknown[]) => creerTiers(...args),
      creerEvenement: (...args: unknown[]) => creerEvenement(...args),
      uploadJustificatif: (...args: unknown[]) => uploadJustificatif(...args),
    },
  };
});

const permState = vi.hoisted(() => ({ allowAll: true, allowed: new Set<string>() }));
vi.mock('@/hooks/usePermissions', () => ({
  usePermissions: () => ({
    has: (p: string) => permState.allowAll || permState.allowed.has(p),
    isLoading: false,
  }),
}));

const tvaState = vi.hoisted(() => ({ on: false }));
vi.mock('@/hooks/useRegimeTva', () => ({ useRegimeTva: () => tvaState.on }));

vi.mock('@/hooks/useActiveAssociation', () => ({
  useActiveAssociation: () => ({ id: 'A', name: 'Asso', role: 'treasurer', status: 'active' }),
}));

// Imported after the mocks so the page picks them up.
import { SaisiePage } from '@/pages/SaisiePage';

const CATEGORIES = [
  {
    id: 'cat-rec',
    sens: 'recette',
    libelle: 'Cotisations',
    compte_id: 'c1',
    journal_id: 'j1',
    is_active: true,
    ordre: 0,
  },
  {
    id: 'cat-dep',
    sens: 'depense',
    libelle: 'Achats',
    compte_id: 'c2',
    journal_id: 'j2',
    is_active: true,
    ordre: 1,
  },
];
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
  {
    id: 'ca',
    numero: '531',
    libelle: 'Caisse',
    type_tresorerie: 'caisse',
    iban: null,
    couleur: null,
    ordre: 1,
    is_active: true,
    solde: '0.00',
  },
];

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/asso/A/saisie']}>
        <Routes>
          <Route path="/asso/:associationId/saisie" element={<SaisiePage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  permState.allowAll = true;
  permState.allowed.clear();
  tvaState.on = false;
  listCategories.mockResolvedValue(CATEGORIES);
  listTresorerie.mockResolvedValue(TRESORERIE);
  listTiers.mockResolvedValue([{ id: 't1', type: 'donateur', nom: 'M. Dupont', is_active: true }]);
  listEvenements.mockResolvedValue([]);
  creerSaisieSimple.mockResolvedValue({ id: 'e7', numero_piece: 7 });
  creerVirement.mockResolvedValue({ id: 'e8', numero_piece: 8 });
  uploadJustificatif.mockResolvedValue({ id: 'j1' });
  creerTiers.mockResolvedValue({
    id: 't-new',
    type: 'fournisseur',
    nom: 'Imprimeur',
    is_active: true,
  });
  creerCategorie.mockResolvedValue({
    id: 'cat-new',
    sens: 'recette',
    libelle: 'Buvette',
    compte_id: 'c',
    journal_id: 'j',
    is_active: true,
    ordre: 9,
  });
});

describe('SaisiePage', () => {
  it('shows only the tabs the user has permission for', async () => {
    // Category management only: the Catégories tab is reachable, Opérations is not.
    permState.allowAll = false;
    permState.allowed.add('categorie:manage');
    renderPage();

    expect(await screen.findByRole('tab', { name: 'Catégories' })).toBeInTheDocument();
    expect(screen.queryByRole('tab', { name: 'Opérations' })).not.toBeInTheDocument();
    expect(screen.queryByRole('tab', { name: 'Tiers' })).not.toBeInTheDocument();
  });

  it('shows the recette categories and treasury accounts once loaded', async () => {
    renderPage();
    expect(await screen.findByRole('option', { name: 'Cotisations' })).toBeInTheDocument();
    expect(await screen.findByRole('option', { name: 'Banque' })).toBeInTheDocument();
    // The depense-only category is filtered out of the default (recette) view.
    expect(screen.queryByRole('option', { name: 'Achats' })).not.toBeInTheDocument();
  });

  it('blocks submission and shows an error when the amount is empty', async () => {
    renderPage();
    await screen.findByRole('option', { name: 'Cotisations' });

    await userEvent.click(screen.getByRole('button', { name: /Enregistrer/ }));

    expect(await screen.findByText('Indiquez un montant.')).toBeInTheDocument();
    expect(creerSaisieSimple).not.toHaveBeenCalled();
  });

  it('quick-adds a category from the saisie screen', async () => {
    renderPage();
    await screen.findByRole('option', { name: 'Cotisations' });

    await userEvent.click(screen.getByRole('button', { name: 'Nouvelle' }));
    const dialog = await screen.findByRole('dialog');
    await userEvent.type(within(dialog).getByLabelText('Libellé'), 'Buvette');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Créer' }));

    await waitFor(() => expect(creerCategorie).toHaveBeenCalledTimes(1));
    expect(creerCategorie).toHaveBeenCalledWith('A', { sens: 'recette', libelle: 'Buvette' });
  });

  it('posts a normalized entry and confirms success on a valid submit', async () => {
    renderPage();
    await screen.findByRole('option', { name: 'Cotisations' });
    await screen.findByRole('option', { name: 'Banque' });

    await userEvent.type(screen.getByLabelText('Montant (€)'), '150,00');
    await userEvent.click(screen.getByRole('button', { name: /Enregistrer/ }));

    await waitFor(() => expect(creerSaisieSimple).toHaveBeenCalledTimes(1));
    const [associationId, input] = creerSaisieSimple.mock.calls[0];
    expect(associationId).toBe('A');
    expect(input).toMatchObject({
      categorie_id: 'cat-rec',
      compte_tresorerie_id: 'bq',
      montant: '150.00',
    });
    expect(input.libelle).toBeUndefined();
    expect(await screen.findByText(/Écriture n° 7 enregistrée/)).toBeInTheDocument();
  });

  it('sends payment metadata from the advanced panel', async () => {
    renderPage();
    await screen.findByRole('option', { name: 'Cotisations' });

    await userEvent.type(screen.getByLabelText('Montant (€)'), '40');
    await userEvent.click(screen.getByRole('button', { name: 'Avancé' }));
    await userEvent.selectOptions(screen.getByLabelText('Mode de règlement'), 'cheque');
    await userEvent.type(screen.getByLabelText('Référence externe'), 'FAC-7');
    await userEvent.click(screen.getByRole('button', { name: /Enregistrer/ }));

    await waitFor(() => expect(creerSaisieSimple).toHaveBeenCalledTimes(1));
    expect(creerSaisieSimple.mock.calls[0][1]).toMatchObject({
      mode_reglement: 'cheque',
      reference_externe: 'FAC-7',
    });
  });

  it('attaches a selected tiers from the advanced panel', async () => {
    renderPage();
    await screen.findByRole('option', { name: 'Cotisations' });

    await userEvent.type(screen.getByLabelText('Montant (€)'), '50');
    await userEvent.click(screen.getByRole('button', { name: 'Avancé' }));
    await userEvent.selectOptions(await screen.findByLabelText('Tiers'), 't1');
    await userEvent.click(screen.getByRole('button', { name: /Enregistrer l’opération/ }));

    await waitFor(() => expect(creerSaisieSimple).toHaveBeenCalledTimes(1));
    expect(creerSaisieSimple.mock.calls[0][1]).toMatchObject({ tiers_id: 't1' });
  });

  it('quick-adds a tiers from the advanced panel', async () => {
    renderPage();
    await screen.findByRole('option', { name: 'Cotisations' });

    await userEvent.click(screen.getByRole('button', { name: 'Avancé' }));
    await userEvent.click(screen.getByRole('button', { name: 'Nouveau tiers' }));
    const dialog = await screen.findByRole('dialog');
    await userEvent.type(within(dialog).getByLabelText('Nom'), 'Imprimeur');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Créer' }));

    await waitFor(() => expect(creerTiers).toHaveBeenCalledTimes(1));
    expect(creerTiers.mock.calls[0][0]).toBe('A');
    expect(creerTiers.mock.calls[0][1]).toMatchObject({ nom: 'Imprimeur', type: 'donateur' });
  });

  it('attaches a selected event from the advanced panel', async () => {
    listEvenements.mockResolvedValue([
      { id: 'ev1', nom: 'Gala 2026', statut: 'actif', couleur: null },
    ]);
    renderPage();
    await screen.findByRole('option', { name: 'Cotisations' });

    await userEvent.type(screen.getByLabelText('Montant (€)'), '50');
    await userEvent.click(screen.getByRole('button', { name: 'Avancé' }));
    await userEvent.selectOptions(await screen.findByLabelText('Événement'), 'ev1');
    await userEvent.click(screen.getByRole('button', { name: /Enregistrer l’opération/ }));

    await waitFor(() => expect(creerSaisieSimple).toHaveBeenCalledTimes(1));
    expect(creerSaisieSimple.mock.calls[0][1]).toMatchObject({ evenement_id: 'ev1' });
  });

  it('quick-adds an event from the advanced panel', async () => {
    creerEvenement.mockResolvedValue({
      id: 'ev-new',
      nom: 'Sortie',
      statut: 'actif',
      couleur: null,
    });
    renderPage();
    await screen.findByRole('option', { name: 'Cotisations' });

    await userEvent.click(screen.getByRole('button', { name: 'Avancé' }));
    await userEvent.click(screen.getByRole('button', { name: 'Nouvel événement' }));
    const dialog = await screen.findByRole('dialog');
    await userEvent.type(within(dialog).getByLabelText('Nom'), 'Sortie');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Créer' }));

    await waitFor(() => expect(creerEvenement).toHaveBeenCalledTimes(1));
    expect(creerEvenement.mock.calls[0][0]).toBe('A');
    expect(creerEvenement.mock.calls[0][1]).toMatchObject({ nom: 'Sortie' });
  });

  it('applies VAT from the advanced panel when the régime is on', async () => {
    tvaState.on = true;
    renderPage();
    await screen.findByRole('option', { name: 'Cotisations' });

    await userEvent.type(screen.getByLabelText('Montant (€)'), '120');
    await userEvent.click(screen.getByRole('button', { name: 'Avancé' }));
    await userEvent.selectOptions(await screen.findByLabelText('TVA'), '20');
    await userEvent.click(screen.getByRole('button', { name: /Enregistrer/ }));

    await waitFor(() => expect(creerSaisieSimple).toHaveBeenCalledTimes(1));
    expect(creerSaisieSimple.mock.calls[0][1]).toMatchObject({ tva_taux: '20' });
  });

  it('hides VAT and never sends a rate while the régime is off', async () => {
    renderPage();
    await screen.findByRole('option', { name: 'Cotisations' });

    await userEvent.type(screen.getByLabelText('Montant (€)'), '50');
    await userEvent.click(screen.getByRole('button', { name: 'Avancé' }));
    expect(screen.queryByLabelText('TVA')).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: /Enregistrer/ }));
    await waitFor(() => expect(creerSaisieSimple).toHaveBeenCalledTimes(1));
    expect(creerSaisieSimple.mock.calls[0][1].tva_taux).toBeUndefined();
  });

  it('posts an internal transfer with source and destination', async () => {
    renderPage();
    await screen.findByRole('option', { name: 'Cotisations' });

    await userEvent.click(screen.getByRole('button', { name: /Virement/ }));
    // Source defaults to a non-bank account (caisse), destination to the bank.
    await userEvent.type(screen.getByLabelText('Montant (€)'), '200,00');
    await userEvent.click(screen.getByRole('button', { name: /Enregistrer le virement/ }));

    await waitFor(() => expect(creerVirement).toHaveBeenCalledTimes(1));
    const [associationId, input] = creerVirement.mock.calls[0];
    expect(associationId).toBe('A');
    expect(input).toMatchObject({
      compte_source_id: 'ca',
      compte_destination_id: 'bq',
      montant: '200.00',
    });
    expect(creerSaisieSimple).not.toHaveBeenCalled();
    expect(await screen.findByText(/Virement n° 8 enregistré/)).toBeInTheDocument();
  });

  it('attaches chosen justificatifs to the created entry', async () => {
    renderPage();
    await screen.findByRole('option', { name: 'Cotisations' });

    await userEvent.type(screen.getByLabelText('Montant (€)'), '60');
    await userEvent.click(screen.getByRole('button', { name: 'Avancé' }));
    const file = new File([new Uint8Array([1, 2, 3])], 'facture.pdf', {
      type: 'application/pdf',
    });
    await userEvent.upload(screen.getByLabelText('Joindre des justificatifs'), file);
    expect(await screen.findByText('facture.pdf')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: /Enregistrer l’opération/ }));

    await waitFor(() => expect(creerSaisieSimple).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(uploadJustificatif).toHaveBeenCalledWith('A', 'e7', file));
    expect(await screen.findByText(/1 justificatif/)).toBeInTheDocument();
  });
});
