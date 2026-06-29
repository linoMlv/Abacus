import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';

import { membersApi, type PermissionInfo, type Preset } from '@/api/members';
import { apiErrorMessage } from '@/api/client';
import { Alert } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

function groupCatalog(catalog: PermissionInfo[]): Array<[string, PermissionInfo[]]> {
  const groups = new Map<string, PermissionInfo[]>();
  for (const info of catalog) {
    const list = groups.get(info.group) ?? [];
    list.push(info);
    groups.set(info.group, list);
  }
  return [...groups.entries()];
}

export function PresetDialog({
  associationId,
  preset,
  open,
  onOpenChange,
}: {
  associationId: string;
  /** The preset to edit, or null to create a new one. */
  preset: Preset | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const queryClient = useQueryClient();

  const catalogQuery = useQuery({
    queryKey: ['permission-catalog', associationId],
    queryFn: () => membersApi.permissionCatalog(associationId),
    enabled: open,
  });

  const [nom, setNom] = useState('');
  const [selected, setSelected] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (open) {
      setNom(preset?.nom ?? '');
      setSelected(new Set(preset?.permissions ?? []));
    }
  }, [open, preset]);

  const save = useMutation({
    mutationFn: () => {
      const payload = { nom: nom.trim(), permissions: [...selected] };
      return preset
        ? membersApi.updatePreset(associationId, preset.id, payload)
        : membersApi.createPreset(associationId, payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['permission-presets', associationId] });
      onOpenChange(false);
    },
  });

  function toggle(value: string, next: boolean) {
    setSelected((prev) => {
      const draft = new Set(prev);
      if (next) draft.add(value);
      else draft.delete(value);
      return draft;
    });
  }

  const catalog = catalogQuery.data ?? [];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogTitle>{preset ? 'Modifier le preset' : 'Nouveau preset'}</DialogTitle>
        <DialogDescription>
          Un preset est un ensemble de permissions réutilisable (rôle sur mesure) que vous pouvez
          assigner à un membre comme base.
        </DialogDescription>

        <form
          className="mt-4 space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (nom.trim()) save.mutate();
          }}
        >
          <div>
            <Label htmlFor="preset-nom">Nom</Label>
            <Input
              id="preset-nom"
              value={nom}
              onChange={(e) => setNom(e.target.value)}
              placeholder="Ex. Équipe Gala"
              autoFocus
              required
            />
          </div>

          <div className="max-h-[44vh] space-y-4 overflow-y-auto pr-1">
            {groupCatalog(catalog).map(([group, items]) => (
              <fieldset key={group} className="space-y-1.5">
                <legend className="text-xs font-semibold uppercase tracking-wide text-faint">
                  {group}
                </legend>
                {items.map((info) => (
                  <label
                    key={info.value}
                    className="flex items-center gap-3 rounded-md px-2 py-1.5 text-sm hover:bg-hover"
                  >
                    <input
                      type="checkbox"
                      className="h-4 w-4 accent-accent"
                      checked={selected.has(info.value)}
                      onChange={(e) => toggle(info.value, e.target.checked)}
                    />
                    <span className="flex-1 text-ink">{info.label}</span>
                  </label>
                ))}
              </fieldset>
            ))}
          </div>

          {save.isError && <Alert>{apiErrorMessage(save, 'Échec de l’enregistrement.')}</Alert>}

          <div className="flex justify-end gap-2 border-t border-hairline pt-4">
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
              Annuler
            </Button>
            <Button type="submit" disabled={save.isPending || !nom.trim()}>
              {save.isPending ? 'Enregistrement…' : 'Enregistrer'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
