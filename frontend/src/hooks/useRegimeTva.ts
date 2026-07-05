import { useQuery } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';

import { associationApi } from '@/api/members';

/**
 * Whether the active association is subject to VAT. Reuses the association
 * context query (same cache key as `usePermissions`), so no extra request. VAT
 * fields/columns stay hidden while this is false — the régime is the single
 * switch that reveals every VAT affordance.
 */
export function useRegimeTva(): boolean {
  const { associationId } = useParams();
  const query = useQuery({
    queryKey: ['association-context', associationId],
    queryFn: () => associationApi.context(associationId as string),
    enabled: !!associationId,
  });
  return query.data?.regime_tva ?? false;
}
