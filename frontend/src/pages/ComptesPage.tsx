import { useSearchParams } from 'react-router-dom';

import { BalanceTab } from '@/components/comptes/BalanceTab';
import { GrandLivreTab } from '@/components/comptes/GrandLivreTab';
import { PlanComptableTab } from '@/components/comptes/PlanComptableTab';
import { RapprochementTab } from '@/components/comptes/RapprochementTab';
import { Card } from '@/components/ui/card';
import { usePermissions } from '@/hooks/usePermissions';
import { PERMISSIONS } from '@/lib/permissions';
import { cn } from '@/lib/utils';

const COMPTES_TABS = [
  {
    key: 'plan',
    label: 'Plan comptable',
    permissions: [PERMISSIONS.REPORT_VIEW, PERMISSIONS.ACCOUNT_MANAGE],
  },
  { key: 'balance', label: 'Balance', permissions: [PERMISSIONS.REPORT_VIEW] },
  { key: 'grand-livre', label: 'Grand livre', permissions: [PERMISSIONS.REPORT_VIEW] },
  { key: 'rapprochement', label: 'Rapprochement', permissions: [PERMISSIONS.REPORT_VIEW] },
] as const;
type CompteTab = (typeof COMPTES_TABS)[number]['key'];

/**
 * Everything the accounts themselves say: the chart (guided edition), the trial
 * balance, one account's ledger, and how the books compare with the bank. Each
 * tab is gated by its own permission and reflected in the URL (`?tab=`) so a
 * ledger can be linked to; an inaccessible tab falls back to the first visible.
 */
export function ComptesPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const { has, isLoading } = usePermissions();

  // While permissions load, show every tab (avoids a flash); the panels and the
  // server still enforce.
  const visibleTabs = COMPTES_TABS.filter((t) => isLoading || t.permissions.some(has));
  const raw = searchParams.get('tab');
  const active: CompteTab | undefined =
    visibleTabs.find((t) => t.key === raw)?.key ?? visibleTabs[0]?.key;

  function selectTab(key: CompteTab) {
    setSearchParams(key === 'plan' ? {} : { tab: key }, { replace: true });
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div>
        <h2 className="text-xl font-semibold tracking-tight text-ink">Comptes</h2>
        <p className="mt-1 text-sm text-muted">
          Le détail comptable : plan de comptes, balance, grand livre et rapprochement bancaire.
        </p>
      </div>

      {active === undefined ? (
        <Card className="p-6 text-sm text-muted">Vous n’avez accès à aucune de ces sections.</Card>
      ) : (
        <>
          <div className="border-b border-hairline">
            <div
              role="tablist"
              aria-label="Sections des comptes"
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

          {active === 'plan' && <PlanComptableTab />}
          {active === 'balance' && <BalanceTab />}
          {active === 'grand-livre' && <GrandLivreTab />}
          {active === 'rapprochement' && <RapprochementTab />}
        </>
      )}
    </div>
  );
}
