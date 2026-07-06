import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, expect, it, vi } from 'vitest';

const list = vi.fn();
const create = vi.fn();
const revoke = vi.fn();
const membersList = vi.fn();

vi.mock('@/api/apikeys', () => ({
  apiKeysApi: {
    list: (...a: unknown[]) => list(...a),
    create: (...a: unknown[]) => create(...a),
    revoke: (...a: unknown[]) => revoke(...a),
  },
}));

vi.mock('@/api/members', () => ({
  membersApi: { list: (...a: unknown[]) => membersList(...a) },
}));

import { ApiKeysPanel } from '@/components/parametres/ApiKeysPanel';

function renderPanel() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ApiKeysPanel associationId="A" />
    </QueryClientProvider>
  );
}

beforeEach(() => {
  list.mockReset();
  create.mockReset();
  revoke.mockReset();
  membersList.mockReset();
  membersList.mockResolvedValue([]);
});

it('lists existing keys with their prefix and never a secret', async () => {
  list.mockResolvedValue([
    {
      id: 'k1',
      name: 'Assistant',
      prefix: 'abk_ab12',
      membership_id: 'm1',
      created_at: '2026-07-01T00:00:00Z',
      last_used_at: null,
      revoked_at: null,
      role: 'viewer',
      member_name: 'Alice',
      member_email: 'a@x.com',
    },
  ]);

  renderPanel();

  expect(await screen.findByText('Assistant')).toBeInTheDocument();
  expect(screen.getByText(/abk_ab12/)).toBeInTheDocument();
});

it('shows the raw key exactly once after creation', async () => {
  list.mockResolvedValue([]);
  create.mockResolvedValue({
    id: 'k2',
    name: 'New',
    prefix: 'abk_zz99',
    membership_id: 'm1',
    created_at: '2026-07-07T00:00:00Z',
    last_used_at: null,
    revoked_at: null,
    role: 'admin',
    member_name: 'Me',
    member_email: 'me@x.com',
    key: 'abk_zz99_the_secret_value',
  });

  renderPanel();
  await screen.findByText('Aucune clé pour l’instant.');

  await userEvent.type(screen.getByLabelText('Nom de la clé'), 'New');
  await userEvent.click(screen.getByRole('button', { name: /Créer une clé/ }));

  await waitFor(() =>
    expect(create).toHaveBeenCalledWith('A', { name: 'New', user_id: undefined })
  );
  expect(await screen.findByText('abk_zz99_the_secret_value')).toBeInTheDocument();
  // The MCP connection hint is shown alongside the one-time secret.
  expect(screen.getByText(/X-API-Key/)).toBeInTheDocument();
});
