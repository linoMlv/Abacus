import { useParams } from 'react-router-dom';

import { Alert } from '@/components/ui/alert';
import { MembresPanel } from '@/components/parametres/MembresPanel';
import { useActiveAssociation } from '@/hooks/useActiveAssociation';
import { useActivePermissions } from '@/hooks/useActivePermissions';

/**
 * Association settings. Today it surfaces the Members tab (members, roles,
 * invitations and per-member permissions / custom presets — T8). Other tabs
 * (exercices, TVA, journaux des accès…) will slot in alongside it.
 */
export function ParametresPage() {
  const { associationId } = useParams() as { associationId: string };
  const association = useActiveAssociation();
  const { has, isLoading } = useActivePermissions(associationId);
  const canManageMembers = has('member:manage');

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h2 className="text-xl font-semibold tracking-tight text-ink">Paramètres</h2>
        <p className="mt-1 text-sm text-muted">{association?.name}</p>
      </div>

      <nav className="flex gap-1 border-b border-hairline" aria-label="Sections des paramètres">
        <span className="border-b-2 border-accent px-3 py-2 text-sm font-medium text-ink">
          Membres
        </span>
      </nav>

      {isLoading ? (
        <p className="text-sm text-muted">Chargement…</p>
      ) : canManageMembers ? (
        <MembresPanel associationId={associationId} />
      ) : (
        <Alert>Vous n’avez pas l’autorisation de gérer les membres de cette association.</Alert>
      )}
    </div>
  );
}
