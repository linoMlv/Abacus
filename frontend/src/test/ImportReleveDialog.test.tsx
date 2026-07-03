import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const importerReleve = vi.fn();
const importerReleveOfx = vi.fn();

vi.mock('@/api/accounting', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/accounting')>();
  return {
    ...actual,
    accountingApi: {
      importerReleve: (...a: unknown[]) => importerReleve(...a),
      importerReleveOfx: (...a: unknown[]) => importerReleveOfx(...a),
    },
  };
});

import { ImportReleveDialog } from '@/components/banque/ImportReleveDialog';

function renderDialog() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ImportReleveDialog
        associationId="A"
        compteId="bq"
        compteLibelle="Compte courant"
        open
        onClose={() => {}}
        onImported={() => {}}
      />
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  importerReleve.mockResolvedValue({ id: 'i1', nb_lignes: 3 });
  importerReleveOfx.mockResolvedValue({ id: 'i2', nb_lignes: 2 });
});

describe('ImportReleveDialog', () => {
  it('imports an OFX file without a column mapping', async () => {
    renderDialog();
    // Switch to OFX: the CSV mapping disappears.
    await userEvent.click(screen.getByRole('button', { name: 'OFX' }));
    expect(screen.queryByLabelText('Séparateur')).not.toBeInTheDocument();

    const file = new File([new Uint8Array([1, 2, 3])], 'releve.ofx', {
      type: 'application/x-ofx',
    });
    await userEvent.upload(screen.getByLabelText(/Fichier/), file);
    await userEvent.click(screen.getByRole('button', { name: 'Importer' }));

    await waitFor(() => expect(importerReleveOfx).toHaveBeenCalledWith('A', 'bq', file));
    expect(importerReleve).not.toHaveBeenCalled();
  });

  it('imports a CSV file with the column mapping', async () => {
    renderDialog();
    const file = new File(['Date;Libelle;Montant\n'], 'releve.csv', { type: 'text/csv' });
    await userEvent.upload(screen.getByLabelText(/Fichier/), file);
    await userEvent.click(screen.getByRole('button', { name: 'Importer' }));

    await waitFor(() => expect(importerReleve).toHaveBeenCalled());
    const [assoc, compte, mapping] = importerReleve.mock.calls[0];
    expect(assoc).toBe('A');
    expect(compte).toBe('bq');
    // 1-based UI columns become 0-based in the API payload.
    expect(mapping).toMatchObject({ date_col: 0, libelle_col: 1, montant_col: 2 });
  });
});
