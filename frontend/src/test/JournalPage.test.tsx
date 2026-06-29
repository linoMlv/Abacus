import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const listEcritures = vi.fn();
const listJournaux = vi.fn();
const listComptes = vi.fn();
const listTresorerie = vi.fn();
const listCategories = vi.fn();
const listTiers = vi.fn();
const listEvenements = vi.fn();
const getEcriture = vi.fn();
const validerEcriture = vi.fn();
const supprimerEcriture = vi.fn();
const validerEcrituresGroupe = vi.fn();
const supprimerEcrituresGroupe = vi.fn();
const listJustificatifs = vi.fn();
const uploadJustificatif = vi.fn();
const supprimerJustificatif = vi.fn();

vi.mock('@/api/accounting', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/accounting')>();
  return {
    ...actual,
    accountingApi: {
      listEcritures: (...a: unknown[]) => listEcritures(...a),
      listJournaux: (...a: unknown[]) => listJournaux(...a),
      listComptes: (...a: unknown[]) => listComptes(...a),
      listTresorerie: (...a: unknown[]) => listTresorerie(...a),
      listCategories: (...a: unknown[]) => listCategories(...a),
      listTiers: (...a: unknown[]) => listTiers(...a),
      listEvenements: (...a: unknown[]) => listEvenements(...a),
      getEcriture: (...a: unknown[]) => getEcriture(...a),
      validerEcriture: (...a: unknown[]) => validerEcriture(...a),
      supprimerEcriture: (...a: unknown[]) => supprimerEcriture(...a),
      validerEcrituresGroupe: (...a: unknown[]) => validerEcrituresGroupe(...a),
      supprimerEcrituresGroupe: (...a: unknown[]) => supprimerEcrituresGroupe(...a),
      listJustificatifs: (...a: unknown[]) => listJustificatifs(...a),
      uploadJustificatif: (...a: unknown[]) => uploadJustificatif(...a),
      supprimerJustificatif: (...a: unknown[]) => supprimerJustificatif(...a),
      justificatifContenuUrl: (assoc: string, id: string) =>
        `/api/asso/${assoc}/justificatifs/${id}/contenu`,
      justificatifApercuUrl: (assoc: string, id: string) =>
        `/api/asso/${assoc}/justificatifs/${id}/apercu`,
      journalPdfUrl: (assoc: string) => `/api/asso/${assoc}/exports/journal.pdf`,
      journalXlsxUrl: (assoc: string) => `/api/asso/${assoc}/exports/journal.xlsx`,
      grandLivrePdfUrl: (assoc: string) => `/api/asso/${assoc}/exports/grand-livre.pdf`,
      grandLivreXlsxUrl: (assoc: string) => `/api/asso/${assoc}/exports/grand-livre.xlsx`,
    },
  };
});

vi.mock('@/hooks/usePermissions', () => ({
  usePermissions: () => ({ has: () => true, isLoading: false }),
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
  listTresorerie.mockResolvedValue([
    {
      id: 'c-bq',
      numero: '512',
      libelle: 'Banque',
      type_tresorerie: 'banque',
      iban: null,
      couleur: null,
      ordre: 0,
      is_active: true,
      solde: '50.00',
    },
  ]);
  listCategories.mockResolvedValue([
    {
      id: 'cat-co',
      sens: 'recette',
      libelle: 'Cotisations',
      compte_id: 'c',
      journal_id: 'j',
      is_active: true,
      ordre: 0,
    },
  ]);
  listTiers.mockResolvedValue([{ id: 't1', type: 'donateur', nom: 'M. Dupont', is_active: true }]);
  listEvenements.mockResolvedValue([{ id: 'ev1', nom: 'Gala', statut: 'actif', couleur: null }]);
  getEcriture.mockResolvedValue(DETAIL);
  validerEcriture.mockResolvedValue({ ...DETAIL, statut: 'validee' });
  listJustificatifs.mockResolvedValue([]);
  uploadJustificatif.mockResolvedValue({
    id: 'j1',
    ecriture_id: 'e2',
    filename: 'facture.pdf',
    content_type: 'application/pdf',
    size: 1234,
    created_at: '2026-06-27T10:00:00Z',
  });
});

describe('JournalPage', () => {
  it('lists the entries with their journal code', async () => {
    renderPage();
    expect(await screen.findByText('Cotisation Mars')).toBeInTheDocument();
    expect(screen.getByText('Loyer')).toBeInTheDocument();
    expect(screen.getByText('VE')).toBeInTheDocument();
  });

  it('refetches with a checked statut facet', async () => {
    renderPage();
    await screen.findByText('Cotisation Mars');

    await userEvent.click(await screen.findByRole('checkbox', { name: 'Brouillon' }));

    await waitFor(() =>
      expect(listEcritures).toHaveBeenCalledWith(
        'A',
        expect.objectContaining({ statut: ['brouillon'] })
      )
    );
  });

  it('refetches with a checked treasury-account facet', async () => {
    renderPage();
    await screen.findByText('Cotisation Mars');

    await userEvent.click(await screen.findByRole('checkbox', { name: 'Banque' }));

    await waitFor(() =>
      expect(listEcritures).toHaveBeenCalledWith(
        'A',
        expect.objectContaining({ compte_id: ['c-bq'] })
      )
    );
  });

  it('combines several checked values into one facet (OR)', async () => {
    renderPage();
    await screen.findByText('Cotisation Mars');

    await userEvent.click(await screen.findByRole('checkbox', { name: 'Recette' }));
    await userEvent.click(screen.getByRole('checkbox', { name: 'Virement' }));

    await waitFor(() =>
      expect(listEcritures).toHaveBeenCalledWith(
        'A',
        expect.objectContaining({ type_operation: ['recette', 'virement'] })
      )
    );
  });

  it('refetches with the category, tiers and date filters', async () => {
    renderPage();
    await screen.findByText('Cotisation Mars');

    await userEvent.click(await screen.findByRole('checkbox', { name: 'Cotisations' }));
    await userEvent.click(screen.getByRole('checkbox', { name: 'M. Dupont' }));
    await userEvent.type(screen.getByLabelText('Date de début'), '2026-06-01');
    await userEvent.type(screen.getByLabelText('Date de fin'), '2026-06-30');

    await waitFor(() =>
      expect(listEcritures).toHaveBeenCalledWith(
        'A',
        expect.objectContaining({
          categorie_id: ['cat-co'],
          tiers_id: ['t1'],
          date_from: '2026-06-01',
          date_to: '2026-06-30',
        })
      )
    );
  });

  it('refetches with the event facet', async () => {
    renderPage();
    await screen.findByText('Cotisation Mars');

    await userEvent.click(await screen.findByRole('checkbox', { name: 'Gala' }));

    await waitFor(() =>
      expect(listEcritures).toHaveBeenCalledWith(
        'A',
        expect.objectContaining({ evenement_id: ['ev1'] })
      )
    );
  });

  it('clears every filter with the reset button', async () => {
    renderPage();
    await screen.findByText('Cotisation Mars');

    const virement = await screen.findByRole('checkbox', { name: 'Virement' });
    await userEvent.click(virement);
    const reset = await screen.findByRole('button', { name: /Réinitialiser/ });
    await userEvent.click(reset);

    await waitFor(() => expect(virement).not.toBeChecked());
    expect(screen.queryByRole('button', { name: /Réinitialiser/ })).not.toBeInTheDocument();
  });

  it('collapses and expands a filter section (accordion)', async () => {
    renderPage();
    await screen.findByText('Cotisation Mars');

    // Sections are expanded by default: the Type options are visible.
    expect(screen.getByRole('checkbox', { name: 'Recette' })).toBeInTheDocument();

    // Collapsing the "Type" section removes its options from the DOM.
    await userEvent.click(screen.getByRole('button', { name: /Type/ }));
    await waitFor(() =>
      expect(screen.queryByRole('checkbox', { name: 'Recette' })).not.toBeInTheDocument()
    );

    // Expanding it again brings them back.
    await userEvent.click(screen.getByRole('button', { name: /Type/ }));
    expect(await screen.findByRole('checkbox', { name: 'Recette' })).toBeInTheDocument();
  });

  it('opens the filters in a drawer on small screens', async () => {
    renderPage();
    await screen.findByText('Cotisation Mars');

    await userEvent.click(screen.getByRole('button', { name: /Filtres/ }));
    const drawer = await screen.findByRole('dialog');
    // The same faceted filters are available inside the drawer.
    expect(within(drawer).getByRole('checkbox', { name: 'Recette' })).toBeInTheDocument();
  });

  it('validates the selected entries in bulk', async () => {
    validerEcrituresGroupe.mockResolvedValue({ traitees: ['e2'], ignorees: [] });
    renderPage();
    await screen.findByText('Cotisation Mars');

    await userEvent.click(
      await screen.findByRole('checkbox', { name: /Sélectionner.*Cotisation Mars/ })
    );
    await userEvent.click(screen.getByRole('button', { name: /Valider la sélection/ }));

    await waitFor(() => expect(validerEcrituresGroupe).toHaveBeenCalledWith('A', ['e2']));
  });

  it('selecting a row does not open the detail drawer', async () => {
    renderPage();
    await screen.findByText('Cotisation Mars');

    await userEvent.click(
      await screen.findByRole('checkbox', { name: /Sélectionner.*Cotisation Mars/ })
    );
    // The detail dialog must not have opened from ticking the row.
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
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

  it('uploads a justificatif from the detail drawer', async () => {
    renderPage();
    await userEvent.click(await screen.findByText('Cotisation Mars'));
    await screen.findByRole('dialog');

    const file = new File([new Uint8Array([1, 2, 3])], 'facture.pdf', {
      type: 'application/pdf',
    });
    await userEvent.upload(screen.getByLabelText('Ajouter un justificatif'), file);

    await waitFor(() => expect(uploadJustificatif).toHaveBeenCalledTimes(1));
    expect(uploadJustificatif).toHaveBeenCalledWith('A', 'e2', file);
  });

  it('previews an existing justificatif in a modal with a download link', async () => {
    listJustificatifs.mockResolvedValue([
      {
        id: 'j9',
        ecriture_id: 'e2',
        filename: 'recu.png',
        content_type: 'image/png',
        size: 2048,
        created_at: '2026-06-27T10:00:00Z',
      },
    ]);
    renderPage();
    await userEvent.click(await screen.findByText('Cotisation Mars'));
    await screen.findByRole('dialog');

    // Click the entry to open the preview modal (no forced download).
    await userEvent.click(await screen.findByRole('button', { name: /Aperçu de recu.png/ }));
    const image = await screen.findByRole('img', { name: 'recu.png' });
    expect(image).toHaveAttribute('src', '/api/asso/A/justificatifs/j9/apercu');
    const link = screen.getByRole('link', { name: /Télécharger/ });
    expect(link).toHaveAttribute('href', '/api/asso/A/justificatifs/j9/contenu');
  });
});
