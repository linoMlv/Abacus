import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus } from 'lucide-react';
import { useState } from 'react';

import type { Role } from '@/api/auth';
import { apiErrorMessage } from '@/api/client';
import { membersApi, type InvitationCreated } from '@/api/members';
import { Alert } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { ROLE_LABELS } from '@/lib/roles';

import { ROLES } from './constants';

export function InvitationsSection({ associationId }: { associationId: string }) {
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
