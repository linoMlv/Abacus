import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useMemo, useState } from 'react';

import { membersApi, type Preset } from '@/api/members';
import { apiErrorMessage } from '@/api/client';
import { Alert } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog';
import { Select } from '@/components/ui/select';
import { groupCatalog } from '@/lib/permissions';
import { ROLE_LABELS } from '@/lib/roles';
import { cn } from '@/lib/utils';

export function MemberPermissionsDialog({
  associationId,
  userId,
  memberName,
  presets,
  open,
  onOpenChange,
}: {
  associationId: string;
  userId: string | null;
  memberName: string;
  presets: Preset[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const queryClient = useQueryClient();

  const catalogQuery = useQuery({
    queryKey: ['permission-catalog', associationId],
    queryFn: () => membersApi.permissionCatalog(associationId),
    enabled: open,
  });

  const permsQuery = useQuery({
    queryKey: ['member-permissions', associationId, userId],
    queryFn: () => membersApi.memberPermissions(associationId, userId as string),
    enabled: open && !!userId,
  });

  // Editable draft: the chosen preset (or none = role) and the minimal set of
  // overrides (deviations from the base). Seeded from the server on open.
  const [presetId, setPresetId] = useState<string | null>(null);
  const [overrides, setOverrides] = useState<Record<string, boolean>>({});

  const member = permsQuery.data;
  useEffect(() => {
    if (member) {
      setPresetId(member.preset_id);
      setOverrides(member.overrides);
    }
  }, [member]);

  const roleBase = useMemo(
    () => new Set(member?.role_permissions ?? []),
    [member?.role_permissions]
  );
  const presetById = useMemo(() => new Map(presets.map((p) => [p.id, p])), [presets]);

  // Base = the selected preset's set, else the built-in role's set.
  const base = useMemo(() => {
    if (presetId) return new Set(presetById.get(presetId)?.permissions ?? []);
    return roleBase;
  }, [presetId, presetById, roleBase]);

  const isEffective = (value: string) => (value in overrides ? overrides[value] : base.has(value));

  function toggle(value: string, next: boolean) {
    setOverrides((prev) => {
      const draft = { ...prev };
      // Only keep an override when it deviates from the base.
      if (next === base.has(value)) delete draft[value];
      else draft[value] = next;
      return draft;
    });
  }

  // When the base (preset) changes, drop overrides that no longer deviate.
  function changePreset(next: string | null) {
    const nextBase = next ? new Set(presetById.get(next)?.permissions ?? []) : roleBase;
    setOverrides((prev) => {
      const draft: Record<string, boolean> = {};
      for (const [k, v] of Object.entries(prev)) {
        if (v !== nextBase.has(k)) draft[k] = v;
      }
      return draft;
    });
    setPresetId(next);
  }

  const save = useMutation({
    mutationFn: () =>
      membersApi.setMemberPermissions(associationId, userId as string, {
        preset_id: presetId,
        overrides,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['member-permissions', associationId] });
      queryClient.invalidateQueries({ queryKey: ['association-context', associationId] });
      onOpenChange(false);
    },
  });

  const overrideCount = Object.keys(overrides).length;
  const groups = useMemo(() => groupCatalog(catalogQuery.data ?? []), [catalogQuery.data]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogTitle>Permissions — {memberName}</DialogTitle>
        <DialogDescription>
          Partez d’un rôle ou d’un preset, puis affinez permission par permission.
        </DialogDescription>

        {permsQuery.isError && (
          <Alert className="mt-4">Impossible de charger les permissions.</Alert>
        )}

        {member?.is_admin ? (
          <Alert className="mt-4">
            {ROLE_LABELS[member.role]} — dispose de toutes les permissions. Pour restreindre cette
            personne, changez d’abord son rôle.
          </Alert>
        ) : member ? (
          <div className="mt-4 space-y-4">
            <div>
              <label
                htmlFor="preset-base"
                className="mb-1.5 block text-xs font-medium text-ink-soft"
              >
                Base
              </label>
              <Select
                id="preset-base"
                value={presetId ?? ''}
                onChange={(e) => changePreset(e.target.value || null)}
              >
                <option value="">Rôle : {ROLE_LABELS[member.role]}</option>
                {presets.map((p) => (
                  <option key={p.id} value={p.id}>
                    Preset : {p.nom}
                  </option>
                ))}
              </Select>
            </div>

            <div className="max-h-[46vh] space-y-4 overflow-y-auto pr-1">
              {groups.map(([group, items]) => (
                <fieldset key={group} className="space-y-1.5">
                  <legend className="text-xs font-semibold uppercase tracking-wide text-faint">
                    {group}
                  </legend>
                  {items.map((info) => {
                    const checked = isEffective(info.value);
                    const overridden = info.value in overrides;
                    return (
                      <label
                        key={info.value}
                        className="flex items-center gap-3 rounded-md px-2 py-1.5 text-sm hover:bg-hover"
                      >
                        <input
                          type="checkbox"
                          className="h-4 w-4 accent-accent"
                          checked={checked}
                          onChange={(e) => toggle(info.value, e.target.checked)}
                        />
                        <span className={cn('flex-1 text-ink', !checked && 'text-muted')}>
                          {info.label}
                        </span>
                        {overridden && (
                          <span className="text-[11px] font-medium text-accent">
                            {checked ? 'ajoutée' : 'retirée'}
                          </span>
                        )}
                      </label>
                    );
                  })}
                </fieldset>
              ))}
            </div>

            {save.isError && <Alert>{apiErrorMessage(save, 'Échec de l’enregistrement.')}</Alert>}

            <div className="flex items-center justify-between gap-3 border-t border-hairline pt-4">
              <p className="text-xs text-muted">
                {overrideCount === 0
                  ? 'Aucune dérogation au rôle/preset'
                  : `${overrideCount} dérogation${overrideCount > 1 ? 's' : ''}`}
              </p>
              <div className="flex gap-2">
                <Button variant="ghost" onClick={() => onOpenChange(false)}>
                  Annuler
                </Button>
                <Button onClick={() => save.mutate()} disabled={save.isPending}>
                  {save.isPending ? 'Enregistrement…' : 'Enregistrer'}
                </Button>
              </div>
            </div>
          </div>
        ) : (
          <p className="mt-4 text-sm text-muted">Chargement…</p>
        )}
      </DialogContent>
    </Dialog>
  );
}
