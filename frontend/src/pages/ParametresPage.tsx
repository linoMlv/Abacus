import { useState } from 'react';
import { useParams } from 'react-router-dom';

import { Alert } from '@/components/ui/alert';
import { ApiKeysPanel } from '@/components/parametres/ApiKeysPanel';
import { ComptabilitePanel } from '@/components/parametres/ComptabilitePanel';
import { ExercicesPanel } from '@/components/parametres/ExercicesPanel';
import { MembresPanel } from '@/components/parametres/MembresPanel';
import { useActiveAssociation } from '@/hooks/useActiveAssociation';
import { usePermissions } from '@/hooks/usePermissions';
import { PERMISSIONS } from '@/lib/permissions';
import { cn } from '@/lib/utils';

type TabId = 'membres' | 'exercices' | 'comptabilite' | 'api';

/**
 * Association settings, organised in permission-gated tabs: Members (members,
 * roles, invitations, per-member permissions — T8) and Exercices (fiscal-year
 * lifecycle: create and close — Phase 2). Other tabs (TVA, journaux des accès…)
 * will slot in alongside them.
 */
export function ParametresPage() {
  const { associationId } = useParams() as { associationId: string };
  const association = useActiveAssociation();
  const { has, isLoading } = usePermissions();

  const tabs: Array<{ id: TabId; label: string; allowed: boolean }> = [
    { id: 'membres', label: 'Membres', allowed: has(PERMISSIONS.MEMBER_MANAGE) },
    {
      id: 'exercices',
      label: 'Exercices',
      allowed: has(PERMISSIONS.EXERCISE_CLOSE) || has(PERMISSIONS.ANNEXE_MANAGE),
    },
    { id: 'comptabilite', label: 'Comptabilité', allowed: has(PERMISSIONS.SETTINGS_MANAGE) },
    { id: 'api', label: 'Clés API / MCP', allowed: has(PERMISSIONS.APIKEY_MANAGE) },
  ];
  const available = tabs.filter((t) => t.allowed);
  const [active, setActive] = useState<TabId>('membres');
  const current = available.find((t) => t.id === active) ?? available[0];

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h2 className="text-xl font-semibold tracking-tight text-ink">Paramètres</h2>
        <p className="mt-1 text-sm text-muted">{association?.name}</p>
      </div>

      {isLoading ? (
        <p className="text-sm text-muted">Chargement…</p>
      ) : available.length === 0 ? (
        <Alert>Vous n’avez pas l’autorisation d’accéder aux paramètres de cette association.</Alert>
      ) : (
        <>
          <nav className="flex gap-1 border-b border-hairline" aria-label="Sections des paramètres">
            {available.map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActive(tab.id)}
                className={cn(
                  'px-3 py-2 text-sm font-medium transition-colors',
                  current?.id === tab.id
                    ? 'border-b-2 border-accent text-ink'
                    : 'text-muted hover:text-ink'
                )}
              >
                {tab.label}
              </button>
            ))}
          </nav>

          {current?.id === 'membres' && <MembresPanel associationId={associationId} />}
          {current?.id === 'exercices' && <ExercicesPanel associationId={associationId} />}
          {current?.id === 'comptabilite' && <ComptabilitePanel associationId={associationId} />}
          {current?.id === 'api' && <ApiKeysPanel associationId={associationId} />}
        </>
      )}
    </div>
  );
}
