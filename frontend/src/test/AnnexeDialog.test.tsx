import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const listAnnexe = vi.fn();
const ajouterRubrique = vi.fn();
const modifierRubrique = vi.fn();
const supprimerRubrique = vi.fn();
const reordonnerAnnexe = vi.fn();

vi.mock('@/api/accounting', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/accounting')>();
  return {
    ...actual,
    accountingApi: {
      listAnnexe: (...a: unknown[]) => listAnnexe(...a),
      ajouterRubrique: (...a: unknown[]) => ajouterRubrique(...a),
      modifierRubrique: (...a: unknown[]) => modifierRubrique(...a),
      supprimerRubrique: (...a: unknown[]) => supprimerRubrique(...a),
      reordonnerAnnexe: (...a: unknown[]) => reordonnerAnnexe(...a),
      annexePdfUrl: () => '/pdf',
    },
  };
});

import { AnnexeDialog } from '@/components/parametres/AnnexeDialog';

const EXERCICE = {
  id: 'ex1',
  libelle: '2026',
  date_debut: '2026-01-01',
  date_fin: '2026-12-31',
  statut: 'ouvert' as const,
  report_a_nouveau_genere: false,
};

function renderDialog() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <AnnexeDialog associationId="A" exercice={EXERCICE} onOpenChange={() => {}} />
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  listAnnexe.mockResolvedValue([
    { id: 'r1', exercice_id: 'ex1', titre: 'Règles et méthodes comptables', contenu: '', ordre: 0 },
    { id: 'r2', exercice_id: 'ex1', titre: 'Faits marquants', contenu: 'RAS', ordre: 1 },
  ]);
  modifierRubrique.mockResolvedValue({});
  ajouterRubrique.mockResolvedValue({});
});

describe('AnnexeDialog', () => {
  it('lists the exercice rubrics', async () => {
    renderDialog();
    expect(await screen.findByText('Annexe — 2026')).toBeInTheDocument();
    expect(await screen.findByDisplayValue('Règles et méthodes comptables')).toBeInTheDocument();
  });

  it('saves an edited rubric body', async () => {
    renderDialog();
    const bodies = await screen.findAllByLabelText('Contenu de la rubrique');
    await userEvent.type(bodies[0], 'Partie double.');
    const saves = screen.getAllByRole('button', { name: 'Enregistrer' });
    await userEvent.click(saves[0]);
    await waitFor(() =>
      expect(modifierRubrique).toHaveBeenCalledWith('A', 'r1', {
        titre: 'Règles et méthodes comptables',
        contenu: 'Partie double.',
      })
    );
  });

  it('adds a rubric', async () => {
    renderDialog();
    await userEvent.click(await screen.findByRole('button', { name: /Ajouter une rubrique/ }));
    await waitFor(() =>
      expect(ajouterRubrique).toHaveBeenCalledWith('A', 'ex1', expect.anything())
    );
  });
});
