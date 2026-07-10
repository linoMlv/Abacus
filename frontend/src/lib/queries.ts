import type { QueryClient } from '@tanstack/react-query';

/**
 * Invalidate every cache an entry mutation (create/edit/correct) affects for an
 * association: the journal listing, the balance, the treasury soldes and the
 * dashboard synthesis. Shared so the set stays defined in one place.
 */
export function invalidateAfterEntry(queryClient: QueryClient, associationId: string): void {
  for (const key of ['ecritures', 'balance', 'tresorerie', 'synthese']) {
    queryClient.invalidateQueries({ queryKey: [key, associationId] });
  }
}
