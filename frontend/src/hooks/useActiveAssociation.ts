import { useParams } from 'react-router-dom';

import type { AssociationSummary } from '@/api/auth';
import { useAuth } from '@/auth/useAuth';

/**
 * The association named in the URL, resolved against the user's memberships —
 * or `undefined` when the URL points at one they do not belong to. Membership
 * is the authorization; the server re-checks it on every request.
 */
export function useActiveAssociation(): AssociationSummary | undefined {
  const { associationId } = useParams();
  const { session } = useAuth();
  return session?.associations.find((a) => a.id === associationId);
}
