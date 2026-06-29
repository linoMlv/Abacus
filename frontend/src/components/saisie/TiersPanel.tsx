import { useQuery } from '@tanstack/react-query';
import { Plus, Users } from 'lucide-react';
import { useState } from 'react';
import { useParams } from 'react-router-dom';

import { accountingApi, TYPE_TIERS_LABELS } from '@/api/accounting';
import { TiersDialog } from '@/components/TiersDialog';
import { Alert } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { usePermissions } from '@/hooks/usePermissions';
import { PERMISSIONS } from '@/lib/permissions';

/** Manage third parties (suppliers, donors, financiers…): list and create. */
export function TiersPanel() {
  const { associationId } = useParams() as { associationId: string };
  const { has } = usePermissions();
  const canManage = has(PERMISSIONS.TIERS_MANAGE);
  const [dialogOpen, setDialogOpen] = useState(false);

  const query = useQuery({
    queryKey: ['tiers', associationId],
    queryFn: () => accountingApi.listTiers(associationId),
  });
  const tiers = query.data ?? [];

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted">
          Vos fournisseurs, donateurs et financeurs, à rattacher aux opérations.
        </p>
        {canManage && (
          <Button variant="accent" size="sm" onClick={() => setDialogOpen(true)}>
            <Plus className="h-4 w-4" aria-hidden />
            Nouveau tiers
          </Button>
        )}
      </div>

      {query.isError ? (
        <Alert>Impossible de charger les tiers.</Alert>
      ) : tiers.length === 0 && !query.isLoading ? (
        <Card className="flex flex-col items-center gap-3 px-6 py-14 text-center">
          <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-accent-soft text-accent">
            <Users className="h-5 w-5" aria-hidden />
          </span>
          <h3 className="text-base font-semibold text-ink">Aucun tiers pour l’instant</h3>
          <p className="max-w-sm text-sm text-muted">
            Ajoutez un fournisseur ou un donateur pour le retrouver lors de la saisie.
          </p>
        </Card>
      ) : (
        <Card className="divide-y divide-hairline">
          {tiers.map((t) => (
            <div key={t.id} className="flex items-center gap-3 px-4 py-3">
              <span className="flex-1 truncate text-sm text-ink">{t.nom}</span>
              <Badge variant="neutral">{TYPE_TIERS_LABELS[t.type]}</Badge>
            </div>
          ))}
        </Card>
      )}

      {canManage && (
        <TiersDialog associationId={associationId} open={dialogOpen} onOpenChange={setDialogOpen} />
      )}
    </div>
  );
}
