import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { DisplayModeProvider } from '@/display/DisplayModeProvider';

const getEcriture = vi.fn();
const listComptes = vi.fn();
const listCategories = vi.fn();
const listTiers = vi.fn();
const listEvenements = vi.fn();
const listJustificatifs = vi.fn();

vi.mock('@/api/accounting', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/accounting')>();
  return {
    ...actual,
    accountingApi: {
      getEcriture: (...a: unknown[]) => getEcriture(...a),
      listComptes: (...a: unknown[]) => listComptes(...a),
      listCategories: (...a: unknown[]) => listCategories(...a),
      listTiers: (...a: unknown[]) => listTiers(...a),
      listEvenements: (...a: unknown[]) => listEvenements(...a),
      listJustificatifs: (...a: unknown[]) => listJustificatifs(...a),
      justificatifContenuUrl: () => '',
      justificatifApercuUrl: () => '',
    },
  };
});

vi.mock('@/hooks/usePermissions', () => ({
  usePermissions: () => ({ has: () => true, isLoading: false }),
}));

import { EcritureDrawer } from '@/components/journal/EcritureDrawer';

const ENTRY = {
  id: 'e1',
  exercice_id: 'x',
  journal_id: 'j-ve',
  categorie_id: 'cat-1',
  date: '2026-06-27',
  numero_piece: 12,
  libelle: 'Cotisation Mars',
  tiers_id: null,
  evenement_id: null,
  reference_externe: null,
  mode_reglement: null,
  statut: 'validee',
  origine: 'saisie_simple',
  extourne_de_id: null,
  recurrence_id: null,
  created_at: '2026-06-27T10:00:00Z',
  validated_at: '2026-06-27T11:00:00Z',
  lignes: [
    { id: 'l1', compte_id: 'c-bq', libelle: 'Cotisation', debit: '150.00', credit: '0.00' },
    { id: 'l2', compte_id: 'c-756', libelle: 'Cotisation', debit: '0.00', credit: '150.00' },
  ],
};

const COMPTES = [
  {
    id: 'c-bq',
    numero: '512',
    libelle: 'Compte courant',
    classe: 5,
    type: 'actif',
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

function renderDrawer(mode: 'simple' | 'avance') {
  localStorage.setItem('abacus:display-mode', mode);
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <DisplayModeProvider>
        <MemoryRouter>
          <EcritureDrawer associationId="A" ecritureId="e1" onClose={() => {}} />
        </MemoryRouter>
      </DisplayModeProvider>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  getEcriture.mockResolvedValue(ENTRY);
  listComptes.mockResolvedValue(COMPTES);
  listCategories.mockResolvedValue([
    { id: 'cat-1', libelle: 'Cotisations', sens: 'recette', is_active: true },
  ]);
  listTiers.mockResolvedValue([]);
  listEvenements.mockResolvedValue([]);
  listJustificatifs.mockResolvedValue([]);
});

describe('EcritureDrawer', () => {
  it('says in plain words what the entry did, by default', async () => {
    renderDrawer('simple');

    expect(await screen.findByText('+150,00 €')).toBeInTheDocument();
    expect(screen.getByText('Reçu sur')).toBeInTheDocument();
    expect(screen.getByText('Compte courant')).toBeInTheDocument();
    expect(screen.queryByText('Débit')).not.toBeInTheDocument();
  });

  it('shows the accounting lines in accounting mode', async () => {
    renderDrawer('avance');

    expect(await screen.findByText('Débit')).toBeInTheDocument();
    expect(screen.getByText('Crédit')).toBeInTheDocument();
    expect(screen.getByText('512 — Compte courant')).toBeInTheDocument();
    expect(screen.getByText('756 — Cotisations')).toBeInTheDocument();
  });
});
