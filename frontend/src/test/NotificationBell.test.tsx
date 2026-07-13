import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const list = vi.fn();
const markRead = vi.fn();
const markAllRead = vi.fn();

vi.mock('@/api/notifications', () => ({
  notificationsApi: {
    list: (...a: unknown[]) => list(...a),
    markRead: (...a: unknown[]) => markRead(...a),
    markAllRead: (...a: unknown[]) => markAllRead(...a),
  },
}));

import { NotificationBell } from '@/components/layout/NotificationBell';

const A_VALIDER = {
  id: 'n1',
  type: 'ecriture_a_valider',
  titre: 'Écriture à valider',
  message: 'Pièce n° 12 — Cotisation Mars',
  lien: '/journal',
  lu_at: null,
  created_at: '2026-07-13T09:00:00Z',
};

function renderBell() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/asso/A/synthese']}>
        <Routes>
          <Route
            path="/asso/:associationId/synthese"
            element={
              <>
                <NotificationBell />
                <span>Synthèse</span>
              </>
            }
          />
          <Route path="/asso/:associationId/journal" element={<span>Journal</span>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  list.mockResolvedValue({ notifications: [A_VALIDER], non_lues: 1 });
  markRead.mockResolvedValue({ ...A_VALIDER, lu_at: '2026-07-13T10:00:00Z' });
  markAllRead.mockResolvedValue({ status: 'ok' });
});

describe('NotificationBell', () => {
  it('counts what is unread', async () => {
    renderBell();

    expect(await screen.findByRole('button', { name: /1 non lues/ })).toBeInTheDocument();
  });

  it('opening a notification marks it read and goes where the work is', async () => {
    const user = userEvent.setup();
    renderBell();
    await user.click(await screen.findByRole('button', { name: /notifications/i }));

    await user.click(await screen.findByText('Écriture à valider'));

    await waitFor(() => expect(markRead).toHaveBeenCalledWith('A', 'n1'));
    expect(await screen.findByText('Journal')).toBeInTheDocument();
  });

  it('says so plainly when nothing awaits', async () => {
    list.mockResolvedValue({ notifications: [], non_lues: 0 });
    const user = userEvent.setup();
    renderBell();

    await user.click(await screen.findByRole('button', { name: /aucune non lue/i }));

    expect(await screen.findByText(/rien ne vous attend/i)).toBeInTheDocument();
  });

  it('marks everything read at once', async () => {
    const user = userEvent.setup();
    renderBell();
    await user.click(await screen.findByRole('button', { name: /notifications/i }));

    await user.click(await screen.findByRole('button', { name: /tout marquer comme lu/i }));

    await waitFor(() => expect(markAllRead).toHaveBeenCalledWith('A'));
  });
});
