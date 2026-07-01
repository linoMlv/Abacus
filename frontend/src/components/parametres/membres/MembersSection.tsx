import { useMutation } from '@tanstack/react-query';
import { Shield, Trash2 } from 'lucide-react';

import type { Role } from '@/api/auth';
import { apiErrorMessage } from '@/api/client';
import { membersApi, type Member } from '@/api/members';
import { Alert } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Select } from '@/components/ui/select';
import { ROLE_LABELS } from '@/lib/roles';

import { ROLES } from './constants';

export function MembersSection({
  associationId,
  members,
  isLoading,
  isError,
  currentUserId,
  onEditPermissions,
  onChanged,
}: {
  associationId: string;
  members: Member[];
  isLoading: boolean;
  isError: boolean;
  currentUserId: string | undefined;
  onEditPermissions: (m: Member) => void;
  onChanged: () => void;
}) {
  const update = useMutation({
    mutationFn: ({
      userId,
      input,
    }: {
      userId: string;
      input: { role?: Role; status?: 'active' | 'suspended' };
    }) => membersApi.updateMember(associationId, userId, input),
    onSuccess: onChanged,
  });
  const remove = useMutation({
    mutationFn: (userId: string) => membersApi.removeMember(associationId, userId),
    onSuccess: onChanged,
  });

  const actionError =
    update.isError || remove.isError
      ? apiErrorMessage(update.isError ? update : remove, 'Action impossible.')
      : null;

  return (
    <section className="space-y-3">
      <div>
        <h3 className="text-sm font-semibold text-ink-soft">Membres</h3>
        <p className="text-sm text-muted">
          Le rôle fixe les permissions de base ; affinez-les ensuite par membre.
        </p>
      </div>

      {actionError && <Alert>{actionError}</Alert>}
      {isError && <Alert>Impossible de charger les membres.</Alert>}

      <Card className="divide-y divide-hairline">
        {isLoading ? (
          <p className="px-4 py-5 text-sm text-muted">Chargement…</p>
        ) : members.length === 0 ? (
          <p className="px-4 py-5 text-sm text-muted">Aucun membre.</p>
        ) : (
          members.map((m) => {
            const isSelf = m.user_id === currentUserId;
            const busy = update.isPending || remove.isPending;
            return (
              <div key={m.user_id} className="flex flex-wrap items-center gap-3 px-4 py-3">
                <div className="min-w-0 flex-1">
                  <p className="flex items-center gap-2 truncate text-sm font-medium text-ink">
                    {m.name}
                    {isSelf && <Badge>Vous</Badge>}
                    {m.status === 'suspended' && <Badge variant="warning">Suspendu</Badge>}
                  </p>
                  <p className="truncate text-xs text-muted">{m.email}</p>
                </div>

                <Select
                  aria-label={`Rôle de ${m.name}`}
                  className="w-44"
                  value={m.role}
                  disabled={busy}
                  onChange={(e) =>
                    update.mutate({ userId: m.user_id, input: { role: e.target.value as Role } })
                  }
                >
                  {ROLES.map((r) => (
                    <option key={r} value={r}>
                      {ROLE_LABELS[r]}
                    </option>
                  ))}
                </Select>

                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => onEditPermissions(m)}
                  title="Permissions"
                >
                  <Shield className="h-4 w-4" aria-hidden />
                  Permissions
                </Button>

                <Button
                  variant="ghost"
                  size="sm"
                  disabled={busy}
                  onClick={() =>
                    update.mutate({
                      userId: m.user_id,
                      input: { status: m.status === 'suspended' ? 'active' : 'suspended' },
                    })
                  }
                >
                  {m.status === 'suspended' ? 'Réactiver' : 'Suspendre'}
                </Button>

                <button
                  type="button"
                  aria-label={`Retirer ${m.name}`}
                  disabled={busy}
                  onClick={() => {
                    if (confirm(`Retirer ${m.name} de l’association ?`)) remove.mutate(m.user_id);
                  }}
                  className="rounded-md p-1.5 text-faint transition-colors hover:bg-depense-soft hover:text-depense focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent disabled:pointer-events-none disabled:opacity-40"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            );
          })
        )}
      </Card>
    </section>
  );
}
