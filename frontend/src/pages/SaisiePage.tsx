import { useSearchParams } from 'react-router-dom';

import { CategoriesPanel } from '@/components/saisie/CategoriesPanel';
import { EvenementsPanel } from '@/components/saisie/EvenementsPanel';
import { OperationForm } from '@/components/saisie/OperationForm';
import { TiersPanel } from '@/components/saisie/TiersPanel';
import { Card } from '@/components/ui/card';
import { usePermissions } from '@/hooks/usePermissions';
import { PERMISSIONS } from '@/lib/permissions';
import { cn } from '@/lib/utils';

const SAISIE_TABS = [
  {
    key: 'operations',
    label: 'Opérations',
    permissions: [PERMISSIONS.ENTRY_CREATE_SIMPLE, PERMISSIONS.ENTRY_CREATE_TRANSFER],
  },
  { key: 'categories', label: 'Catégories', permissions: [PERMISSIONS.CATEGORIE_MANAGE] },
  { key: 'tiers', label: 'Tiers', permissions: [PERMISSIONS.TIERS_MANAGE] },
  { key: 'evenements', label: 'Événements', permissions: [PERMISSIONS.EVENT_MANAGE] },
] as const;
type SaisieTab = (typeof SAISIE_TABS)[number]['key'];

/**
 * The "create / modify" hub: operations plus the management of the things an
 * operation references (categories, tiers, events). Each tab is gated by its own
 * permission, so a user only sees the sections they can use (e.g. someone who can
 * manage categories but not enter operations still reaches the Catégories tab).
 * The active tab is reflected in the URL (`?tab=`) for deep links; an inaccessible
 * one falls back to the first the user can see.
 */
export function SaisiePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const { has, isLoading } = usePermissions();

  // While permissions load, show every tab (avoids a flash); the panels and the
  // server still enforce. Otherwise only the tabs the user has a permission for.
  const visibleTabs = SAISIE_TABS.filter((t) => isLoading || t.permissions.some(has));
  const raw = searchParams.get('tab');
  const active: SaisieTab | undefined =
    visibleTabs.find((t) => t.key === raw)?.key ?? visibleTabs[0]?.key;

  function selectTab(key: SaisieTab) {
    setSearchParams(key === 'operations' ? {} : { tab: key }, { replace: true });
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h2 className="text-xl font-semibold tracking-tight text-ink">Saisie</h2>
        <p className="mt-1 text-sm text-muted">
          Enregistrez vos opérations et gérez catégories, tiers et événements.
        </p>
      </div>

      {active === undefined ? (
        <Card className="p-6 text-sm text-muted">
          Vous n’avez accès à aucune section de saisie.
        </Card>
      ) : (
        <>
          <div className="border-b border-hairline">
            <div
              role="tablist"
              aria-label="Sections de saisie"
              className="-mb-px flex flex-wrap gap-1"
            >
              {visibleTabs.map((t) => (
                <button
                  key={t.key}
                  type="button"
                  role="tab"
                  aria-selected={active === t.key}
                  onClick={() => selectTab(t.key)}
                  className={cn(
                    'border-b-2 px-3.5 py-2 text-sm font-medium transition-colors',
                    active === t.key
                      ? 'border-accent text-accent'
                      : 'border-transparent text-muted hover:text-ink'
                  )}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>

          {active === 'operations' && <OperationForm mode="create" />}
          {active === 'categories' && <CategoriesPanel />}
          {active === 'tiers' && <TiersPanel />}
          {active === 'evenements' && <EvenementsPanel />}
        </>
      )}
    </div>
  );
}
