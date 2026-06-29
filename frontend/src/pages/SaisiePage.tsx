import { useSearchParams } from 'react-router-dom';

import { CategoriesPanel } from '@/components/saisie/CategoriesPanel';
import { EvenementsPanel } from '@/components/saisie/EvenementsPanel';
import { OperationForm } from '@/components/saisie/OperationForm';
import { TiersPanel } from '@/components/saisie/TiersPanel';
import { cn } from '@/lib/utils';

const SAISIE_TABS = [
  { key: 'operations', label: 'Opérations' },
  { key: 'categories', label: 'Catégories' },
  { key: 'tiers', label: 'Tiers' },
  { key: 'evenements', label: 'Événements' },
] as const;
type SaisieTab = (typeof SAISIE_TABS)[number]['key'];

/**
 * The "create / modify" hub: operations plus the management of the things an
 * operation references (categories, tiers, events). The active tab is reflected
 * in the URL (`?tab=`) so deep links (e.g. "manage events" from the dashboard)
 * land on the right section.
 */
export function SaisiePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const raw = searchParams.get('tab');
  const active: SaisieTab = SAISIE_TABS.some((t) => t.key === raw)
    ? (raw as SaisieTab)
    : 'operations';

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

      <div className="border-b border-hairline">
        <div role="tablist" aria-label="Sections de saisie" className="-mb-px flex flex-wrap gap-1">
          {SAISIE_TABS.map((t) => (
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
    </div>
  );
}
