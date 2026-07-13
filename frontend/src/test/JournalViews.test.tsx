import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { DisplayModeProvider } from '@/display/DisplayModeProvider';
import { DisplayModeToggle } from '@/display/DisplayModeToggle';

const listEcritures = vi.fn();
const listJournaux = vi.fn();
const listTresorerie = vi.fn();
const listCategories = vi.fn();
const listTiers = vi.fn();
const listEvenements = vi.fn();

vi.mock('@/api/accounting', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/accounting')>();
  return {
    ...actual,
    accountingApi: {
      listEcritures: (...a: unknown[]) => listEcritures(...a),
      listJournaux: (...a: unknown[]) => listJournaux(...a),
      listTresorerie: (...a: unknown[]) => listTresorerie(...a),
      listCategories: (...a: unknown[]) => listCategories(...a),
      listTiers: (...a: unknown[]) => listTiers(...a),
      listEvenements: (...a: unknown[]) => listEvenements(...a),
      journalPdfUrl: (assoc: string) => `/api/asso/${assoc}/exports/journal.pdf`,
      journalXlsxUrl: (assoc: string) => `/api/asso/${assoc}/exports/journal.xlsx`,
    },
  };
});

vi.mock('@/hooks/usePermissions', () => ({
  usePermissions: () => ({ has: () => true, isLoading: false }),
}));

import { JournalPage } from '@/pages/JournalPage';

const RECETTE = {
  id: 'e1',
  exercice_id: 'x',
  journal_id: 'j-ve',
  categorie_id: 'cat-1',
  date: '2026-06-27',
  numero_piece: 12,
  libelle: 'Cotisation Mars',
  tiers_id: 'tiers-1',
  evenement_id: null,
  reference_externe: null,
  mode_reglement: null,
  statut: 'validee',
  origine: 'saisie_simple',
  extourne_de_id: null,
  recurrence_id: null,
  created_at: '2026-06-27T10:00:00Z',
  validated_at: '2026-06-27T11:00:00Z',
  montant: '150.00',
  journal_code: 'VE',
  sens: 'recette',
  compte_libelle: 'Compte courant',
  compte_contrepartie_libelle: null,
  montant_tresorerie: '150.00',
  lignes: [
    {
      compte_id: 'c-bq',
      compte_numero: '512',
      compte_libelle: 'Compte courant',
      libelle: 'Cotisation Mars',
      debit: '150.00',
      credit: '0.00',
    },
    {
      compte_id: 'c-756',
      compte_numero: '756',
      compte_libelle: 'Cotisations',
      libelle: 'Cotisation Mars',
      debit: '0.00',
      credit: '150.00',
    },
  ],
};

const DEPENSE = {
  ...RECETTE,
  id: 'e2',
  numero_piece: 13,
  libelle: 'Ramette papier',
  categorie_id: 'cat-2',
  tiers_id: null,
  journal_code: 'AC',
  sens: 'depense',
  montant: '80.00',
  montant_tresorerie: '-80.00',
  lignes: [],
};

/** The page under the app-wide toggle, exactly as the shell renders it (topbar). */
function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <DisplayModeProvider>
        <DisplayModeToggle />
        <MemoryRouter initialEntries={['/asso/A/journal']}>
          <Routes>
            <Route path="/asso/:associationId/journal" element={<JournalPage />} />
          </Routes>
        </MemoryRouter>
      </DisplayModeProvider>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  listEcritures.mockResolvedValue([RECETTE, DEPENSE]);
  listJournaux.mockResolvedValue([{ id: 'j-ve', code: 'VE', libelle: 'Ventes' }]);
  listTresorerie.mockResolvedValue([]);
  listCategories.mockResolvedValue([
    { id: 'cat-1', libelle: 'Cotisations', sens: 'recette', is_active: true },
    { id: 'cat-2', libelle: 'Fournitures', sens: 'depense', is_active: true },
  ]);
  listTiers.mockResolvedValue([{ id: 'tiers-1', nom: 'M. Dupont', type: 'donateur' }]);
  listEvenements.mockResolvedValue([]);
});

describe('Journal — vue simple (par défaut)', () => {
  it('reads without jargon: sens, tags and signed amount, no débit/crédit', async () => {
    renderPage();

    expect(await screen.findByText('Cotisation Mars')).toBeInTheDocument();
    expect(screen.getByText('+150,00 €')).toBeInTheDocument();
    expect(screen.getByText('−80,00 €')).toBeInTheDocument();
    expect(screen.getAllByText('Compte courant').length).toBeGreaterThan(0);
    // Category and tiers are named, not encoded.
    expect(screen.getByText('Cotisations')).toBeInTheDocument();
    expect(screen.getByText('M. Dupont')).toBeInTheDocument();
    // No accountant's columns.
    expect(screen.queryByRole('columnheader', { name: 'Débit' })).not.toBeInTheDocument();
    expect(screen.queryByRole('columnheader', { name: 'Crédit' })).not.toBeInTheDocument();
  });
});

describe('Journal — vue comptable', () => {
  it('reveals débit/crédit, the voucher and the entry lines once switched on', async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText('Cotisation Mars');

    await user.click(screen.getByRole('switch', { name: /mode comptable/i }));

    expect(await screen.findByRole('columnheader', { name: 'Débit' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Crédit' })).toBeInTheDocument();
    expect(screen.getByText('12')).toBeInTheDocument(); // n° de pièce
    expect(screen.getByText('756')).toBeInTheDocument(); // compte de contrepartie
  });

  it('remembers the choice for the next visit', async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText('Cotisation Mars');

    await user.click(screen.getByRole('switch', { name: /mode comptable/i }));

    await waitFor(() => expect(localStorage.getItem('abacus:display-mode')).toBe('avance'));
  });
});
