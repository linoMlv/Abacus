import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { membersApi, type Member } from '@/api/members';
import { useAuth } from '@/auth/useAuth';

import { MemberPermissionsDialog } from './MemberPermissionsDialog';
import { InvitationsSection } from './membres/InvitationsSection';
import { MembersSection } from './membres/MembersSection';
import { PresetsSection } from './membres/PresetsSection';

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
