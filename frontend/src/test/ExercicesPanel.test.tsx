import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const listExercices = vi.fn();
const getSynthese = vi.fn();
const cloturerExercice = vi.fn();
const creerExercice = vi.fn();

vi.mock('@/api/accounting', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/accounting')>();
  return {
    ...actual,
    accountingApi: {
      listExercices: (...a: unknown[]) => listExercices(...a),
      getSynthese: (...a: unknown[]) => getSynthese(...a),
      cloturerExercice: (...a: unknown[]) => cloturerExercice(...a),
      creerExercice: (...a: unknown[]) => creerExercice(...a),
    },
  };
});

import { ExercicesPanel } from '@/components/parametres/ExercicesPanel';

function renderPanel() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ExercicesPanel associationId="A" />
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  listExercices.mockResolvedValue([
    {
      id: 'ex1',
      libelle: '2026',
      date_debut: '2026-01-01',
      date_fin: '2026-12-31',
      statut: 'ouvert',
      report_a_nouveau_genere: false,
    },
  ]);
  getSynthese.mockResolvedValue({
    resultat: { recettes: '300.00', depenses: '100.00', resultat: '200.00' },
  });
  cloturerExercice.mockResolvedValue({
    resultat: '200.00',
    report_a_nouveau: '200.00',
    reserves: '0',
    exercice_cloture: {},
    exercice_suivant: {},
  });
});

describe('ExercicesPanel', () => {
  it('lists fiscal years with their status', async () => {
    renderPanel();
    expect(await screen.findByText('2026')).toBeInTheDocument();
    expect(screen.getByText('Ouvert')).toBeInTheDocument();
  });

  it('closes a fiscal year with the affectation defaulted to report à nouveau', async () => {
    renderPanel();
    await userEvent.click(await screen.findByRole('button', { name: /Clôturer/ }));

    // The result is shown, defaulted entirely to report à nouveau.
    expect(await screen.findByText(/excédent/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: /Clôturer l’exercice/ }));
    await waitFor(() =>
      expect(cloturerExercice).toHaveBeenCalledWith('A', 'ex1', {
        report_a_nouveau: '200.00',
        reserves: '0',
      })
    );
  });
});
