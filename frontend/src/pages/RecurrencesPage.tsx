import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CalendarClock, Pencil, Play, Plus, Repeat, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { useParams } from 'react-router-dom';

import {
  accountingApi,
  PERIODICITE_LABELS,
  type Recurrence,
  RECURRENCE_MODE_LABELS,
} from '@/api/accounting';
import { RecurrenceDialog } from '@/components/recurrences/RecurrenceDialog';
import { Alert } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { usePermissions } from '@/hooks/usePermissions';
import { formatDate, formatEUR } from '@/lib/format';
import { PERMISSIONS } from '@/lib/permissions';

export function RecurrencesPage() {
  const { associationId } = useParams() as { associationId: string };
  const { has } = usePermissions();
  const canManage = has(PERMISSIONS.RECURRENCE_MANAGE);
  const queryClient = useQueryClient();
  const [dialog, setDialog] = useState<{ recurrence?: Recurrence } | null>(null);
  const [generated, setGenerated] = useState<number | null>(null);

  const query = useQuery({
    queryKey: ['recurrences', associationId],
    queryFn: () => accountingApi.listRecurrences(associationId),
  });
  const recurrences = query.data ?? [];

  const generer = useMutation({
    mutationFn: () => accountingApi.genererRecurrences(associationId),
    onSuccess: (res) => {
      setGenerated(res.generees);
      queryClient.invalidateQueries({ queryKey: ['recurrences', associationId] });
      queryClient.invalidateQueries({ queryKey: ['ecritures', associationId] });
    },
  });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold tracking-tight text-ink">Récurrences</h2>
          <p className="text-sm text-muted">
            Loyers, abonnements, cotisations… générés automatiquement chaque jour à l’échéance.
          </p>
        </div>
        {canManage && (
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => generer.mutate()} disabled={generer.isPending}>
              <Play className="h-4 w-4" aria-hidden />
              {generer.isPending ? 'Génération…' : 'Générer les échéances dues'}
            </Button>
            <Button variant="accent" onClick={() => setDialog({})}>
              <Plus className="h-4 w-4" aria-hidden />
              Nouvelle récurrence
            </Button>
          </div>
        )}
      </div>

      {generated !== null && (
        <Alert className="border-recette/20 bg-recette-soft text-recette">
          {generated === 0
            ? 'Aucune échéance due aujourd’hui.'
            : `${generated} écriture(s) générée(s).`}
        </Alert>
      )}

      {query.isError ? (
        <Alert>Impossible de charger les récurrences.</Alert>
      ) : query.isLoading ? (
        <RecurrencesSkeleton />
      ) : recurrences.length === 0 ? (
        <Card className="p-8 text-center">
          <Repeat className="mx-auto h-8 w-8 text-faint" aria-hidden />
          <p className="mt-3 text-sm text-muted">
            Aucune récurrence. Créez-en une pour automatiser vos opérations répétées.
          </p>
        </Card>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {recurrences.map((r) => (
            <RecurrenceCard
              key={r.id}
              associationId={associationId}
              recurrence={r}
              canManage={canManage}
              onEdit={() => setDialog({ recurrence: r })}
            />
          ))}
        </div>
      )}

      {dialog && canManage && (
        <RecurrenceDialog
          associationId={associationId}
          recurrence={dialog.recurrence}
          open
          onClose={() => setDialog(null)}
        />
      )}
    </div>
  );
}

function RecurrenceCard({
  associationId,
  recurrence,
  canManage,
  onEdit,
}: {
  associationId: string;
  recurrence: Recurrence;
  canManage: boolean;
  onEdit: () => void;
}) {
  const queryClient = useQueryClient();
  const [confirmDelete, setConfirmDelete] = useState(false);
  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ['recurrences', associationId] });

  const toggle = useMutation({
    mutationFn: (actif: boolean) =>
      accountingApi.modifierRecurrence(associationId, recurrence.id, { actif }),
    onSuccess: invalidate,
  });
  const remove = useMutation({
    mutationFn: () => accountingApi.supprimerRecurrence(associationId, recurrence.id),
    onSuccess: invalidate,
  });

  return (
    <Card className={`p-4 ${recurrence.actif ? '' : 'opacity-60'}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate font-medium text-ink">{recurrence.libelle}</p>
          <p className="mt-0.5 flex items-center gap-1.5 text-xs text-muted">
            <CalendarClock className="h-3.5 w-3.5" aria-hidden />
            {PERIODICITE_LABELS[recurrence.periodicite]} · prochaine{' '}
            {formatDate(recurrence.prochaine_echeance)}
          </p>
        </div>
        <span className="shrink-0 font-mono text-sm font-semibold tabular-nums text-ink">
          {formatEUR(recurrence.montant)}
        </span>
      </div>

      <div className="mt-3 flex items-center justify-between">
        <div className="flex gap-1.5">
          <Badge variant={recurrence.mode === 'auto' ? 'accent' : 'neutral'}>
            {RECURRENCE_MODE_LABELS[recurrence.mode]}
          </Badge>
          {!recurrence.actif && <Badge variant="neutral">En pause</Badge>}
        </div>
        {canManage && (
          <div className="flex gap-1">
            <Button
              size="sm"
              variant="ghost"
              onClick={() => toggle.mutate(!recurrence.actif)}
              disabled={toggle.isPending}
            >
              {recurrence.actif ? 'Mettre en pause' : 'Réactiver'}
            </Button>
            <Button size="sm" variant="ghost" onClick={onEdit} aria-label="Modifier">
              <Pencil className="h-4 w-4" aria-hidden />
            </Button>
            {confirmDelete ? (
              <Button
                size="sm"
                variant="danger"
                onClick={() => remove.mutate()}
                disabled={remove.isPending}
              >
                Confirmer
              </Button>
            ) : (
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setConfirmDelete(true)}
                aria-label="Supprimer"
              >
                <Trash2 className="h-4 w-4" aria-hidden />
              </Button>
            )}
          </div>
        )}
      </div>
    </Card>
  );
}

function RecurrencesSkeleton() {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {Array.from({ length: 4 }).map((_, i) => (
        <Card key={i} className="p-4">
          <div className="h-4 w-1/2 animate-pulse rounded bg-hairline" />
          <div className="mt-3 h-3 w-2/3 animate-pulse rounded bg-hairline" />
        </Card>
      ))}
    </div>
  );
}
