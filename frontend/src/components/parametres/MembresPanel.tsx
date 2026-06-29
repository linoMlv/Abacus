import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { KeyRound, Pencil, Plus, Shield, Trash2 } from 'lucide-react';
import { useState } from 'react';

import { apiErrorMessage } from '@/api/client';
import { membersApi, type InvitationCreated, type Member, type Preset } from '@/api/members';
import type { Role } from '@/api/auth';
import { useAuth } from '@/auth/useAuth';
import { Alert } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { ROLE_LABELS } from '@/lib/roles';
import { cn } from '@/lib/utils';
import { MemberPermissionsDialog } from './MemberPermissionsDialog';
import { PresetDialog } from './PresetDialog';

const ROLES: Role[] = ['admin', 'accountant', 'treasurer', 'viewer'];

export function MembresPanel({ associationId }: { associationId: string }) {
  const { session } = useAuth();
  const currentUserId = session?.user.id;
  const queryClient = useQueryClient();

  const membersQuery = useQuery({
    queryKey: ['members', associationId],
    queryFn: () => membersApi.list(associationId),
  });
  const presetsQuery = useQuery({
    queryKey: ['permission-presets', associationId],
    queryFn: () => membersApi.listPresets(associationId),
  });

  const [permFor, setPermFor] = useState<Member | null>(null);

  const presets = presetsQuery.data ?? [];

  return (
    <div className="space-y-8">
      <MembersSection
        associationId={associationId}
        members={membersQuery.data ?? []}
        isLoading={membersQuery.isLoading}
        isError={membersQuery.isError}
        currentUserId={currentUserId}
        onEditPermissions={setPermFor}
        onChanged={() => queryClient.invalidateQueries({ queryKey: ['members', associationId] })}
      />

      <InvitationsSection associationId={associationId} />

      <PresetsSection associationId={associationId} presets={presets} />

      <MemberPermissionsDialog
        associationId={associationId}
        userId={permFor?.user_id ?? null}
        memberName={permFor?.name ?? ''}
        presets={presets}
        open={permFor !== null}
        onOpenChange={(open) => !open && setPermFor(null)}
      />
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Members
// --------------------------------------------------------------------------- //
function MembersSection({
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

// --------------------------------------------------------------------------- //
// Invitations
// --------------------------------------------------------------------------- //
function InvitationsSection({ associationId }: { associationId: string }) {
  const queryClient = useQueryClient();
  const [email, setEmail] = useState('');
  const [role, setRole] = useState<Role>('treasurer');
  const [lastLink, setLastLink] = useState<string | null>(null);

  const invitationsQuery = useQuery({
    queryKey: ['invitations', associationId],
    queryFn: () => membersApi.listInvitations(associationId),
  });

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ['invitations', associationId] });

  const create = useMutation({
    mutationFn: () => membersApi.createInvitation(associationId, { email: email.trim(), role }),
    onSuccess: (inv: InvitationCreated) => {
      setEmail('');
      setLastLink(`${window.location.origin}/invitation?token=${inv.token}`);
      invalidate();
    },
  });
  const revoke = useMutation({
    mutationFn: (id: string) => membersApi.revokeInvitation(associationId, id),
    onSuccess: invalidate,
  });

  const invitations = invitationsQuery.data ?? [];

  return (
    <section className="space-y-3">
      <div>
        <h3 className="text-sm font-semibold text-ink-soft">Invitations</h3>
        <p className="text-sm text-muted">
          Invitez par e-mail ; la personne rejoint l’association en acceptant.
        </p>
      </div>

      <Card className="space-y-4 p-4">
        <form
          className="flex flex-wrap items-end gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (email.trim()) create.mutate();
          }}
        >
          <div className="min-w-[12rem] flex-1">
            <label htmlFor="invite-email" className="mb-1 block text-xs font-medium text-ink-soft">
              E-mail
            </label>
            <Input
              id="invite-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="personne@exemple.org"
              required
            />
          </div>
          <div>
            <label htmlFor="invite-role" className="mb-1 block text-xs font-medium text-ink-soft">
              Rôle
            </label>
            <Select
              id="invite-role"
              className="w-44"
              value={role}
              onChange={(e) => setRole(e.target.value as Role)}
            >
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {ROLE_LABELS[r]}
                </option>
              ))}
            </Select>
          </div>
          <Button type="submit" disabled={create.isPending || !email.trim()}>
            <Plus className="h-4 w-4" aria-hidden />
            Inviter
          </Button>
        </form>

        {create.isError && <Alert>{apiErrorMessage(create, 'Invitation impossible.')}</Alert>}
        {lastLink && (
          <div className="rounded-lg border border-recette/20 bg-recette-soft px-3.5 py-2.5 text-sm text-recette">
            Invitation envoyée. Lien à partager :{' '}
            <code className="break-all text-xs">{lastLink}</code>
          </div>
        )}

        {invitations.length > 0 && (
          <ul className="divide-y divide-hairline">
            {invitations.map((inv) => (
              <li key={inv.id} className="flex items-center gap-3 py-2.5">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm text-ink">{inv.email}</p>
                  <p className="text-xs text-muted">{ROLE_LABELS[inv.role]}</p>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={revoke.isPending}
                  onClick={() => revoke.mutate(inv.id)}
                >
                  Révoquer
                </Button>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </section>
  );
}

// --------------------------------------------------------------------------- //
// Presets (custom roles)
// --------------------------------------------------------------------------- //
function PresetsSection({ associationId, presets }: { associationId: string; presets: Preset[] }) {
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
