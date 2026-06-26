import { useState } from 'react';
import { Navigate, Outlet, useParams } from 'react-router-dom';

import { useAuth } from '@/auth/useAuth';

import { Sidebar } from './Sidebar';
import { Topbar } from './Topbar';

/**
 * Authenticated application frame. The URL names the active association, but
 * membership is the authorization: a non-member is bounced to the home picker
 * (the server independently enforces this on every request).
 */
export function AppShell() {
  const { associationId } = useParams();
  const { session } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);

  const isMember = session?.associations.some((a) => a.id === associationId);
  if (!isMember) return <Navigate to="/" replace />;

  return (
    <div className="flex min-h-dvh bg-canvas">
      <div className="hidden lg:block">
        <Sidebar />
      </div>

      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            type="button"
            aria-label="Fermer la navigation"
            className="absolute inset-0 bg-ink/40"
            onClick={() => setMobileOpen(false)}
          />
          <div className="absolute inset-y-0 left-0 shadow-xl">
            <Sidebar onNavigate={() => setMobileOpen(false)} />
          </div>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar onMenu={() => setMobileOpen(true)} />
        <main className="flex-1 px-6 py-7 lg:px-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
