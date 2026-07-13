import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Bell } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import { type Notification, notificationsApi } from '@/api/notifications';
import { formatDate } from '@/lib/format';
import { cn } from '@/lib/utils';

/**
 * What awaits this person, here (C28). It is where the alerts that used to sit on
 * the Synthèse now live: the dashboard tells you where the association stands, the
 * bell tells you what is yours to do — two different questions.
 *
 * Each notification links to the screen where the thing gets settled, and reading
 * it marks it read; the server decides what appears at all.
 */
export function NotificationBell() {
  const { associationId } = useParams() as { associationId: string };
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);

  const query = useQuery({
    queryKey: ['notifications', associationId],
    queryFn: () => notificationsApi.list(associationId),
    // The bell reflects state others change (a colleague leaves a draft): refresh
    // it when the window comes back into focus rather than polling in the dark.
    refetchOnWindowFocus: true,
  });
  const notifications = query.data?.notifications ?? [];
  const unread = query.data?.non_lues ?? 0;

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ['notifications', associationId] });

  const markRead = useMutation({
    mutationFn: (id: string) => notificationsApi.markRead(associationId, id),
    onSuccess: invalidate,
  });
  const markAllRead = useMutation({
    mutationFn: () => notificationsApi.markAllRead(associationId),
    onSuccess: invalidate,
  });

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (!panelRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false);
    document.addEventListener('mousedown', onClick);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onClick);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  function openNotification(notification: Notification) {
    if (notification.lu_at === null) markRead.mutate(notification.id);
    setOpen(false);
    if (notification.lien) navigate(`/asso/${associationId}${notification.lien}`);
  }

  return (
    <div className="relative" ref={panelRef}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-haspopup="menu"
        aria-label={
          unread > 0 ? `Notifications (${unread} non lues)` : 'Notifications (aucune non lue)'
        }
        className="relative flex h-9 w-9 items-center justify-center rounded-lg text-ink-soft transition-colors hover:bg-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
      >
        <Bell className="h-5 w-5" aria-hidden />
        {unread > 0 && (
          <span className="absolute -right-0.5 -top-0.5 inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-accent px-1 text-[10px] font-semibold text-white">
            {unread > 9 ? '9+' : unread}
          </span>
        )}
      </button>

      {open && (
        <div
          role="menu"
          aria-label="Notifications"
          className="absolute right-0 top-11 z-40 w-80 overflow-hidden rounded-xl border border-hairline bg-surface shadow-lg"
        >
          <div className="flex items-center justify-between border-b border-hairline px-4 py-2.5">
            <h3 className="text-sm font-semibold text-ink">Notifications</h3>
            {unread > 0 && (
              <button
                type="button"
                onClick={() => markAllRead.mutate()}
                disabled={markAllRead.isPending}
                className="text-xs font-medium text-accent hover:underline"
              >
                Tout marquer comme lu
              </button>
            )}
          </div>

          <div className="max-h-96 overflow-y-auto">
            {query.isLoading ? (
              <p className="px-4 py-6 text-sm text-muted">Chargement…</p>
            ) : notifications.length === 0 ? (
              <p className="px-4 py-6 text-sm text-muted">Rien ne vous attend. Tout est à jour.</p>
            ) : (
              notifications.map((n) => (
                <button
                  key={n.id}
                  type="button"
                  role="menuitem"
                  onClick={() => openNotification(n)}
                  className={cn(
                    'flex w-full flex-col items-start gap-0.5 border-b border-hairline px-4 py-3 text-left last:border-0 hover:bg-hover',
                    n.lu_at === null && 'bg-accent-soft/40'
                  )}
                >
                  <span className="flex w-full items-center gap-2">
                    {n.lu_at === null && (
                      <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-accent" aria-hidden />
                    )}
                    <span className="flex-1 text-sm font-medium text-ink">{n.titre}</span>
                    <span className="shrink-0 text-xs text-faint">{formatDate(n.created_at)}</span>
                  </span>
                  {n.message && <span className="text-xs text-muted">{n.message}</span>}
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
