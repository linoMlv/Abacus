import { createContext, useContext } from 'react';

import type { Session } from '@/api/auth';

export interface AuthContextValue {
  /** Current session, or null when signed out. */
  session: Session | null;
  /** True while the initial session lookup is in flight. */
  isLoading: boolean;
  /** Re-fetch the session (after login/logout or membership changes). */
  refresh: () => void;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth doit être utilisé dans un <AuthProvider>.');
  return ctx;
}
