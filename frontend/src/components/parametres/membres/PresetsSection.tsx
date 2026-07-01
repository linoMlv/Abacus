import { useMutation, useQueryClient } from '@tanstack/react-query';
import { KeyRound, Pencil, Plus, Trash2 } from 'lucide-react';
import { useState } from 'react';

import { membersApi, type Preset } from '@/api/members';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { cn } from '@/lib/utils';

import { PresetDialog } from '../PresetDialog';

export function PresetsSection({
  associationId,
  presets,
}: {
  associationId: string;
  presets: Preset[];
}) {
  const queryClient = useQueryClient();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Preset | null>(null);

  const remove = useMutation({
    mutationFn: (id: string) => membersApi.deletePreset(associationId, id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['permission-presets', associationId] });
      queryClient.invalidateQueries({ queryKey: ['members', associationId] });
    },
  });

  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-ink-soft">Presets de permissions</h3>
          <p className="text-sm text-muted">Des rôles sur mesure, réutilisables par membre.</p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            setEditing(null);
            setDialogOpen(true);
          }}
        >
          <Plus className="h-4 w-4" aria-hidden />
          Nouveau preset
        </Button>
      </div>

      <Card className="divide-y divide-hairline">
        {presets.length === 0 ? (
          <p className="px-4 py-5 text-sm text-muted">
            Aucun preset. Créez-en un pour assigner rapidement un ensemble de permissions.
          </p>
        ) : (
          presets.map((p) => (
            <div key={p.id} className={cn('flex items-center gap-3 px-4 py-3')}>
              <KeyRound className="h-4 w-4 shrink-0 text-faint" aria-hidden />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-ink">{p.nom}</p>
                <p className="text-xs text-muted">
                  {p.permissions.length} permission{p.permissions.length > 1 ? 's' : ''}
                </p>
              </div>
              <button
                type="button"
                aria-label={`Modifier ${p.nom}`}
                onClick={() => {
                  setEditing(p);
                  setDialogOpen(true);
                }}
                className="rounded-md p-1.5 text-faint transition-colors hover:bg-hover hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
              >
                <Pencil className="h-4 w-4" />
              </button>
              <button
                type="button"
                aria-label={`Supprimer ${p.nom}`}
                disabled={remove.isPending}
                onClick={() => {
                  if (confirm(`Supprimer le preset « ${p.nom} » ?`)) remove.mutate(p.id);
                }}
                className="rounded-md p-1.5 text-faint transition-colors hover:bg-depense-soft hover:text-depense focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent disabled:pointer-events-none disabled:opacity-40"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          ))
        )}
      </Card>

      <PresetDialog
        associationId={associationId}
        preset={editing}
        open={dialogOpen}
        onOpenChange={setDialogOpen}
      />
    </section>
  );
}
