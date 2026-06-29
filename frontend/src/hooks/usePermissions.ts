import { useQuery } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';

import { associationApi } from '@/api/members';
import type { Permission } from '@/lib/permissions';

/**
 * The signed-in user's server-authoritative effective permissions in the active
 * association (role/preset base ± overrides; admin = all), fetched from the
 * association context. `has(...)` drives all UI gating so a permission change
 * takes effect immediately — the server still enforces every permission, so this
 * only hides/disables affordances the user cannot use.
 */
export function usePermissions() {
  const { associationId } = useParams();
  const query = useQuery({
    queryKey: ['association-context', associationId],
    queryFn: () => associationApi.context(associationId as string),
    enabled: !!associationId,
  });
  const permissions = query.data?.permissions;
  return {
    isLoading: query.isLoading,
    has: (permission: Permission) => permissions?.includes(permission) ?? false,
  };
}
