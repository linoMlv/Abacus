import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, expect, it, vi } from 'vitest';

const list = vi.fn();
const listPresets = vi.fn();
const listInvitations = vi.fn();
const updateMember = vi.fn();
const permissionCatalog = vi.fn();
const memberPermissions = vi.fn();
const setMemberPermissions = vi.fn();

vi.mock('@/api/members', () => ({
  membersApi: {
    list: (...a: unknown[]) => list(...a),
    listPresets: (...a: unknown[]) => listPresets(...a),
    listInvitations: (...a: unknown[]) => listInvitations(...a),
    updateMember: (...a: unknown[]) => updateMember(...a),
    removeMember: vi.fn(),
    createInvitation: vi.fn(),
    revokeInvitation: vi.fn(),
    permissionCatalog: (...a: unknown[]) => permissionCatalog(...a),
    memberPermissions: (...a: unknown[]) => memberPermissions(...a),
    setMemberPermissions: (...a: unknown[]) => setMemberPermissions(...a),
    createPreset: vi.fn(),
    updatePreset: vi.fn(),
    deletePreset: vi.fn(),
  },
}));

let canManage = true;
vi.mock('@/hooks/useActivePermissions', () => ({
  useActivePermissions: () => ({
    has: (p: string) => (p === 'member:manage' ? canManage : false),
    isLoading: false,
  }),
}));

vi.mock('@/hooks/useActiveAssociation', () => ({
  useActiveAssociation: () => ({ id: 'A', name: 'Mon Asso', role: 'admin', status: 'active' }),
}));

vi.mock('@/auth/useAuth', () => ({
  useAuth: () => ({ session: { user: { id: 'me' }, associations: [] }, isLoading: false }),
}));

import { ParametresPage } from '@/pages/ParametresPage';

const CATALOG = [
  { value: 'dashboard:view', group: 'Consultation', label: 'Voir la synthèse' },
  { value: 'report:view', group: 'Consultation', label: 'Voir les états' },
  { value: 'event:manage', group: 'Gestion', label: 'Gérer les événements' },
];

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/asso/A/parametres']}>
        <Routes>
          <Route path="/asso/:associationId/parametres" element={<ParametresPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  canManage = true;
  list.mockResolvedValue([
    { user_id: 'u1', email: 'pat@ex.org', name: 'Pat', role: 'viewer', status: 'active' },
  ]);
  listPresets.mockResolvedValue([]);
  listInvitations.mockResolvedValue([]);
  updateMember.mockResolvedValue({});
  permissionCatalog.mockResolvedValue(CATALOG);
  memberPermissions.mockResolvedValue({
    user_id: 'u1',
    role: 'viewer',
    is_admin: false,
    preset_id: null,
    role_permissions: ['dashboard:view', 'report:view'],
    base_permissions: ['dashboard:view', 'report:view'],
    overrides: {},
    effective: ['dashboard:view', 'report:view'],
  });
  setMemberPermissions.mockResolvedValue({});
});

it('hides the panel when the user cannot manage members', async () => {
  canManage = false;
  renderPage();
  expect(await screen.findByText(/pas l’autorisation/)).toBeInTheDocument();
  expect(list).not.toHaveBeenCalled();
});

it('lists members and changes a role', async () => {
  renderPage();
  await screen.findByText('Pat');

  await userEvent.selectOptions(screen.getByLabelText('Rôle de Pat'), 'treasurer');
  await waitFor(() => expect(updateMember).toHaveBeenCalledWith('A', 'u1', { role: 'treasurer' }));
});

it('grants a permission via the member permissions dialog', async () => {
  renderPage();
  await screen.findByText('Pat');

  await userEvent.click(screen.getByRole('button', { name: 'Permissions' }));
  // The dialog loads the member's permissions + catalog.
  const eventToggle = await screen.findByRole('checkbox', { name: /Gérer les événements/ });
  expect(eventToggle).not.toBeChecked();

  await userEvent.click(eventToggle);
  await userEvent.click(screen.getByRole('button', { name: 'Enregistrer' }));

  await waitFor(() =>
    expect(setMemberPermissions).toHaveBeenCalledWith('A', 'u1', {
      preset_id: null,
      overrides: { 'event:manage': true },
    })
  );
});
