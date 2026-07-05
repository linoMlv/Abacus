import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, expect, it, vi } from 'vitest';

const context = vi.fn();
const updateSettings = vi.fn();

vi.mock('@/api/members', () => ({
  associationApi: {
    context: (...a: unknown[]) => context(...a),
    updateSettings: (...a: unknown[]) => updateSettings(...a),
  },
}));

import { ComptabilitePanel } from '@/components/parametres/ComptabilitePanel';

function renderPanel() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ComptabilitePanel associationId="A" />
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  context.mockResolvedValue({
    id: 'A',
    name: 'Asso',
    role: 'admin',
    regime_tva: false,
    permissions: [],
  });
  updateSettings.mockResolvedValue({
    id: 'A',
    name: 'Asso',
    role: 'admin',
    regime_tva: true,
    permissions: [],
  });
});

it('reflects the current régime and toggles it', async () => {
  renderPanel();
  const toggle = (await screen.findByRole('checkbox')) as HTMLInputElement;
  expect(toggle.checked).toBe(false);

  await userEvent.click(toggle);
  await waitFor(() => expect(updateSettings).toHaveBeenCalledWith('A', { regime_tva: true }));
  expect(await screen.findByText('Activé')).toBeInTheDocument();
});
