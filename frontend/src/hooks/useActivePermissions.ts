import { useQuery } from '@tanstack/react-query';

import { associationApi } from '@/api/members';

/**
 * The signed-in user's server-authoritative effective permissions in the active
 * association (role/preset base ± overrides; admin = all). Use `has(...)` to gate
 * UI — the server independently enforces every permission, so this only hides
 * affordances the user cannot use.
 */
export function useActivePermissions(associationId: string | undefined) {
  const query = useQuery({
    queryKey: ['association-context', associationId],
    queryFn: () => associationApi.context(associationId as string),
    enabled: !!associationId,
  });
  const permissions = query.data?.permissions;
  return {
    isLoading: query.isLoading,
    has: (permission: string) => permissions?.includes(permission) ?? false,
  };
}
