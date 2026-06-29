import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, expect, it, vi } from 'vitest';

const invitationPreview = vi.fn();
const acceptInvitation = vi.fn();
const login = vi.fn();
const logout = vi.fn();

vi.mock('@/api/auth', () => ({
  authApi: {
    invitationPreview: (...a: unknown[]) => invitationPreview(...a),
    acceptInvitation: (...a: unknown[]) => acceptInvitation(...a),
    login: (...a: unknown[]) => login(...a),
    logout: (...a: unknown[]) => logout(...a),
  },
}));

const refresh = vi.fn();
let session: { user: { id: string; email: string } } | null = null;
vi.mock('@/auth/useAuth', () => ({
  useAuth: () => ({ session, refresh, isLoading: false }),
}));

const navigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => navigate };
});

import { AcceptInvitationPage } from '@/pages/auth/AcceptInvitationPage';

const PREVIEW = {
  association_id: 'asso-1',
  association_name: 'Les Amis',
  email: 'guest@ex.org',
  role: 'treasurer' as const,
};

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/invitation?token=tok123']}>
        <Routes>
          <Route path="/invitation" element={<AcceptInvitationPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  session = null;
  invitationPreview.mockResolvedValue(PREVIEW);
  acceptInvitation.mockResolvedValue({ user: { id: 'u', email: PREVIEW.email }, associations: [] });
  login.mockResolvedValue({ user: { id: 'u', email: PREVIEW.email }, associations: [] });
  logout.mockResolvedValue(undefined);
});

it('creates the invited account and joins', async () => {
  renderPage();
  await screen.findByText('Les Amis');

  await userEvent.click(screen.getByRole('tab', { name: /Créer un compte/ }));
  await userEvent.type(screen.getByLabelText('Nom complet'), 'Guest');
  await userEvent.type(screen.getByLabelText('Mot de passe'), 'password123');
  await userEvent.click(screen.getByRole('button', { name: /Créer mon compte et rejoindre/ }));

  await waitFor(() =>
    expect(acceptInvitation).toHaveBeenCalledWith({
      token: 'tok123',
      name: 'Guest',
      password: 'password123',
    })
  );
  await waitFor(() =>
    expect(navigate).toHaveBeenCalledWith('/asso/asso-1/synthese', { replace: true })
  );
});

it('signs in then joins for an existing account', async () => {
  renderPage();
  await screen.findByText('Les Amis');

  await userEvent.type(screen.getByLabelText('Mot de passe'), 'password123');
  await userEvent.click(screen.getByRole('button', { name: /Se connecter et rejoindre/ }));

  await waitFor(() =>
    expect(login).toHaveBeenCalledWith({ email: 'guest@ex.org', password: 'password123' })
  );
  await waitFor(() => expect(acceptInvitation).toHaveBeenCalledWith({ token: 'tok123' }));
});

it('one-click joins when signed in as the invited account', async () => {
  session = { user: { id: 'u', email: PREVIEW.email } };
  renderPage();

  await userEvent.click(await screen.findByRole('button', { name: /Rejoindre Les Amis/ }));
  await waitFor(() => expect(acceptInvitation).toHaveBeenCalledWith({ token: 'tok123' }));
});

it('blocks joining when signed in as a different account', async () => {
  session = { user: { id: 'other', email: 'someone@else.org' } };
  renderPage();

  expect(await screen.findByText(/destinée à/)).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /Rejoindre Les Amis/ })).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: /Se déconnecter pour continuer/ })).toBeInTheDocument();
});
