import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useMemo, type ReactNode } from 'react';

import { authApi } from '@/api/auth';

import { AuthContext } from './useAuth';

/**
 * Loads the session once and shares it. A failed lookup (401 when signed out)
 * resolves to "no session" rather than an error, so the app simply shows the
 * login screen.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ['session'],
    queryFn: authApi.session,
    retry: false,
    staleTime: 60_000,
  });

  const value = useMemo(
    () => ({
      session: data ?? null,
      isLoading,
      refresh: () => queryClient.invalidateQueries({ queryKey: ['session'] }),
    }),
    [data, isLoading, queryClient]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
