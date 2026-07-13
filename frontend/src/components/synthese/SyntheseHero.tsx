import { TrendingDown, TrendingUp } from 'lucide-react';
import { lazy, Suspense } from 'react';

import type { CompteTresorerie, CourbePoint } from '@/api/accounting';
import { Card } from '@/components/ui/card';
import { formatEUR } from '@/lib/format';
import { cn } from '@/lib/utils';

// The curve carries recharts, so it loads lazily inside the eager hero: the
// consolidated number and the account chips paint immediately, the trend fills in.
const TreasuryCurve = lazy(() => import('@/components/charts/TreasuryCurve'));

/** Fallback swatch colour for an account with no colour set (the treasury accent). */
const TREASURY_TINT = '#2563eb';

interface Props {
  total: number;
  comptes: CompteTresorerie[];
  courbe: CourbePoint[];
}

/**
 * The Synthèse hero: the association's consolidated treasury, a big tabular
 * figure (IBM Plex Mono — the "registre" identity) sitting on its own evolution
 * curve, with the period's movement called out and one chip per account. It
 * answers, at a glance, "how much do we have, and which way is it heading".
 */
export function SyntheseHero({ total, comptes, courbe }: Props) {
  const delta =
    courbe.length >= 2 ? Number(courbe[courbe.length - 1].solde) - Number(courbe[0].solde) : null;
  const up = (delta ?? 0) >= 0;

  return (
    <Card className="overflow-hidden p-5 sm:p-6">
      <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <p className="text-[11px] font-medium uppercase tracking-wide text-muted">
            Trésorerie consolidée
          </p>
          <p className="mt-1 font-mono text-3xl font-semibold tabular text-ink">
            {formatEUR(total)}
          </p>
          {delta !== null && (
            <p
              className={cn(
                'mt-1 flex items-center gap-1 text-sm',
                up ? 'text-recette' : 'text-depense'
              )}
            >
              {up ? (
                <TrendingUp className="h-4 w-4" aria-hidden />
              ) : (
                <TrendingDown className="h-4 w-4" aria-hidden />
              )}
              <span className="tabular">
                {up ? '+' : '−'}
                {formatEUR(Math.abs(delta))}
              </span>
              <span className="text-muted">sur la période</span>
            </p>
          )}
        </div>
        {courbe.length >= 2 && (
          <div className="h-24 w-full sm:h-28 sm:max-w-md" aria-hidden>
            <Suspense
              fallback={<div className="h-full w-full animate-pulse rounded-lg bg-hover" />}
            >
              <TreasuryCurve points={courbe} />
            </Suspense>
          </div>
        )}
      </div>

      {comptes.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-2 border-t border-hairline pt-4">
          {comptes.map((c) => (
            <span
              key={c.id}
              className="inline-flex items-center gap-1.5 rounded-full bg-canvas px-2.5 py-1 text-xs"
            >
              <span
                className="h-2 w-2 rounded-full"
                style={{ backgroundColor: c.couleur ?? TREASURY_TINT }}
                aria-hidden
              />
              <span className="text-ink-soft">{c.libelle}</span>
              <span className="tabular font-medium text-ink">{formatEUR(c.solde)}</span>
            </span>
          ))}
        </div>
      )}
    </Card>
  );
}
