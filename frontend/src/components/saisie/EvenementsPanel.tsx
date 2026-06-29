import { useQuery } from '@tanstack/react-query';
import { CalendarRange, Plus } from 'lucide-react';
import { useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';

import { accountingApi, type Evenement } from '@/api/accounting';
import { EvenementDialog } from '@/components/EvenementDialog';
import { EvenementCard, EvenementDetail } from '@/components/evenements/EvenementCard';
import { Alert } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { usePermissions } from '@/hooks/usePermissions';
import { PERMISSIONS } from '@/lib/permissions';

/** Manage events (create / edit) and inspect their budget vs réalisé. */
export function EvenementsPanel() {
  const { associationId } = useParams() as { associationId: string };
  const { has } = usePermissions();
  const canManage = has(PERMISSIONS.EVENT_MANAGE);

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Evenement | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);

  const query = useQuery({
    queryKey: ['evenements', associationId],
    queryFn: () => accountingApi.listEvenements(associationId),
  });
  const evenements = useMemo(() => query.data ?? [], [query.data]);
  const open = openId ? (evenements.find((e) => e.id === openId) ?? null) : null;

  function openCreate() {
    setEditing(null);
    setDialogOpen(true);
  }
  function openEdit(evenement: Evenement) {
    setEditing(evenement);
    setDialogOpen(true);
  }

  return (
    <div className="space-y-5">
      {open ? (
        <EvenementDetail
          associationId={associationId}
          evenement={open}
          onBack={() => setOpenId(null)}
          onEdit={canManage ? () => openEdit(open) : undefined}
        />
      ) : (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-muted">
              Suivez les recettes et dépenses de vos actions, budget à l’appui.
            </p>
            {canManage && (
              <Button variant="accent" size="sm" onClick={openCreate}>
                <Plus className="h-4 w-4" aria-hidden />
                Nouvel événement
              </Button>
            )}
          </div>

          {query.isError ? (
            <Alert>Impossible de charger les événements.</Alert>
          ) : evenements.length === 0 && !query.isLoading ? (
            <EmptyState canManage={canManage} onCreate={openCreate} />
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {evenements.map((evenement) => (
                <EvenementCard
                  key={evenement.id}
                  evenement={evenement}
                  onOpen={() => setOpenId(evenement.id)}
                  onEdit={canManage ? () => openEdit(evenement) : undefined}
                />
              ))}
            </div>
          )}
        </>
      )}

      {canManage && (
        <EvenementDialog
          associationId={associationId}
          evenement={editing}
          open={dialogOpen}
          onOpenChange={setDialogOpen}
        />
      )}
    </div>
  );
}

function EmptyState({ canManage, onCreate }: { canManage: boolean; onCreate: () => void }) {
  return (
    <Card className="flex flex-col items-center gap-3 px-6 py-14 text-center">
      <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-accent-soft text-accent">
        <CalendarRange className="h-5 w-5" aria-hidden />
      </span>
      <h3 className="text-base font-semibold text-ink">Aucun événement pour l’instant</h3>
      <p className="max-w-sm text-sm text-muted">
        Créez un événement (Gala, sortie, tournoi…) puis rattachez-y vos opérations pour suivre son
        budget.
      </p>
      {canManage && (
        <Button variant="accent" onClick={onCreate}>
          <Plus className="h-4 w-4" aria-hidden />
          Nouvel événement
        </Button>
      )}
    </Card>
  );
}
