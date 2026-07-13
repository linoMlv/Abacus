import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, expect, it, vi } from 'vitest';

const listEcritures = vi.fn();

vi.mock('@/api/accounting', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/accounting')>();
  return {
    ...actual,
    accountingApi: {
      listEcritures: (...args: unknown[]) => listEcritures(...args),
    },
  };
});

import {
  type DrilldownSegment,
  OperationsDrilldownDialog,
} from '@/components/synthese/OperationsDrilldownDialog';

function row(over: Record<string, unknown> = {}) {
  return {
    id: 'e1',
    exercice_id: 'x',
    journal_id: 'j',
    categorie_id: 'cat',
    tiers_id: null,
    evenement_id: null,
    date: '2026-03-04',
    numero_piece: 12,
    libelle: 'Achat de fournitures',
    reference_externe: null,
    mode_reglement: null,
    statut: 'validee',
    origine: 'saisie_simple',
    extourne_de_id: null,
    created_at: '2026-03-04',
    validated_at: '2026-03-04',
    montant: '89.90',
    journal_code: 'AC',
    ...over,
  };
}

const SEGMENT: DrilldownSegment = {
  title: 'Fournitures',
  subtitle: 'Dépenses · période',
  total: 89.9,
  tone: 'depense',
  filter: { categorie_id: ['cat'], date_from: '2026-01-01', date_to: '2026-12-31' },
};

function renderDialog(segment: DrilldownSegment | null, open = true) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <OperationsDrilldownDialog
        associationId="A"
        segment={segment}
        open={open}
        onOpenChange={() => {}}
      />
    </QueryClientProvider>
  );
}

beforeEach(() => {
  listEcritures.mockReset();
});

it('queries listEcritures with the segment filter and lists the operations', async () => {
  listEcritures.mockResolvedValue([row()]);
  renderDialog(SEGMENT);

  await waitFor(() =>
    expect(listEcritures).toHaveBeenCalledWith('A', {
      categorie_id: ['cat'],
      date_from: '2026-01-01',
      date_to: '2026-12-31',
    })
  );
  expect(await screen.findByText('Achat de fournitures')).toBeInTheDocument();
  expect(screen.getByRole('dialog')).toHaveTextContent('Fournitures');
});

it('shows an empty state when the segment has no operation', async () => {
  listEcritures.mockResolvedValue([]);
  renderDialog(SEGMENT);
  expect(await screen.findByText(/aucune opération/i)).toBeInTheDocument();
});

it('does not query while the dialog is closed', () => {
  listEcritures.mockResolvedValue([]);
  renderDialog(SEGMENT, false);
  expect(listEcritures).not.toHaveBeenCalled();
});
