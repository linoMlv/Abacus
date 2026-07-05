import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { associationApi } from '@/api/members';
import { apiErrorMessage } from '@/api/client';
import { Alert } from '@/components/ui/alert';
import { Card } from '@/components/ui/card';

/**
 * Accounting settings for the association. For now: the VAT régime switch — off
 * by default (most associations are exempt); turning it on reveals every VAT
 * affordance (rate at saisie, category defaults, état de TVA). SETTINGS_MANAGE.
 */
export function ComptabilitePanel({ associationId }: { associationId: string }) {
  const queryClient = useQueryClient();
  const contextQuery = useQuery({
    queryKey: ['association-context', associationId],
    queryFn: () => associationApi.context(associationId),
  });
  const regimeTva = contextQuery.data?.regime_tva ?? false;

  const mutation = useMutation({
    mutationFn: (next: boolean) => associationApi.updateSettings(associationId, { regime_tva: next }),
    onSuccess: (ctx) => {
      queryClient.setQueryData(['association-context', associationId], ctx);
    },
  });

  const error = apiErrorMessage(mutation, 'Enregistrement impossible.');

  return (
    <div className="space-y-4">
      <Card className="p-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h3 className="text-sm font-semibold text-ink">Régime de TVA</h3>
            <p className="mt-1 text-sm text-muted">
              Activez si l’association est assujettie à la TVA. La TVA apparaît alors à la
              saisie (montants TTC) et un état de TVA devient disponible dans les rapports.
            </p>
          </div>
          <label className="inline-flex shrink-0 items-center gap-2 text-sm">
            <input
              type="checkbox"
              className="h-4 w-4 accent-accent"
              checked={regimeTva}
              disabled={mutation.isPending || contextQuery.isLoading}
              onChange={(e) => mutation.mutate(e.target.checked)}
            />
            <span className="font-medium text-ink">{regimeTva ? 'Activé' : 'Désactivé'}</span>
          </label>
        </div>
        {error && (
          <div className="mt-4">
            <Alert>{error}</Alert>
          </div>
        )}
      </Card>
    </div>
  );
}
