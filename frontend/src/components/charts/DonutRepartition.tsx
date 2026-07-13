import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';

import type { DonutSlice } from '@/lib/chartColors';
import { formatEUR } from '@/lib/format';
import { cn } from '@/lib/utils';

interface Props {
  slices: DonutSlice[];
  total: number;
  /** Label shown in the donut's hole, above the total. */
  centerLabel: string;
  /** Fired when a slice is activated from the legend or the ring. */
  onSelect?: (slice: DonutSlice) => void;
  /** Message shown when there is nothing to plot. */
  emptyHint?: string;
}

const prefersReducedMotion =
  typeof window !== 'undefined' &&
  typeof window.matchMedia === 'function' &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches;

function share(value: number, total: number): string {
  if (total <= 0) return '0 %';
  return `${Math.round((value / total) * 100)} %`;
}

/**
 * Part-to-whole donut for a Synthèse répartition. The legend is the primary,
 * keyboard-reachable surface: each entry names its slice, its amount and its
 * share (identity is never colour-alone — the "relief" rule the categorical
 * palette requires), and activating it (or clicking the ring) drills into the
 * segment's operations. Default export so it rides the lazy `charts` chunk with
 * recharts, never the main bundle.
 */
export default function DonutRepartition({
  slices,
  total,
  centerLabel,
  onSelect,
  emptyHint,
}: Props) {
  if (slices.length === 0) {
    // Keep the donut's footprint (a light-grey ring at 0 €) so paired donuts stay
    // aligned even when one side has no entry over the period.
    return (
      <div className="flex flex-col items-center gap-5 sm:flex-row sm:gap-6">
        <div className="relative h-44 w-44 shrink-0">
          <div className="h-full w-full rounded-full border-[18px] border-hover" aria-hidden />
          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center text-center">
            <span className="max-w-[6rem] truncate text-[11px] uppercase tracking-wide text-muted">
              {centerLabel}
            </span>
            <span className="tabular text-base font-semibold text-faint">{formatEUR(0)}</span>
          </div>
        </div>
        <p className="flex-1 text-sm text-muted">{emptyHint ?? 'Aucune entrée.'}</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center gap-5 sm:flex-row sm:gap-6">
      <div className="relative h-44 w-44 shrink-0">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={slices as unknown as Record<string, unknown>[]}
              dataKey="value"
              nameKey="label"
              innerRadius="64%"
              outerRadius="88%"
              paddingAngle={slices.length > 1 ? 2 : 0}
              stroke="var(--color-surface)"
              strokeWidth={2}
              isAnimationActive={!prefersReducedMotion}
              onClick={(entry) => onSelect?.(entry as unknown as DonutSlice)}
            >
              {slices.map((s) => (
                <Cell
                  key={s.id}
                  fill={s.color}
                  className={onSelect ? 'cursor-pointer' : undefined}
                />
              ))}
            </Pie>
            <Tooltip
              content={({ active, payload }) =>
                active && payload?.length ? (
                  <div className="rounded-lg border border-hairline bg-surface px-3 py-2 text-xs shadow-lg shadow-ink/5">
                    <p className="mb-0.5 text-muted">{payload[0].payload.label}</p>
                    <p className="tabular font-semibold text-ink">
                      {formatEUR(Number(payload[0].value))}
                      <span className="ml-1.5 font-normal text-muted">
                        {share(Number(payload[0].value), total)}
                      </span>
                    </p>
                  </div>
                ) : null
              }
            />
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center text-center">
          <span className="max-w-[6rem] truncate text-[11px] uppercase tracking-wide text-muted">
            {centerLabel}
          </span>
          <span className="tabular text-base font-semibold text-ink">{formatEUR(total)}</span>
        </div>
      </div>

      <ul className="w-full min-w-0 flex-1 space-y-1">
        {slices.map((slice) => (
          <li key={slice.id}>
            <button
              type="button"
              onClick={() => onSelect?.(slice)}
              disabled={!onSelect}
              className={cn(
                'flex w-full items-center gap-2.5 rounded-lg px-2 py-1.5 text-left transition-colors',
                onSelect
                  ? 'hover:bg-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent'
                  : 'cursor-default'
              )}
              aria-label={`${slice.label} : ${formatEUR(slice.value)}, ${share(slice.value, total)}`}
            >
              <span
                className="h-2.5 w-2.5 shrink-0 rounded-full"
                style={{ backgroundColor: slice.color }}
                aria-hidden
              />
              <span className="min-w-0 flex-1 truncate text-sm text-ink">{slice.label}</span>
              <span className="tabular shrink-0 text-sm font-medium text-ink">
                {formatEUR(slice.value)}
              </span>
              <span className="tabular w-12 shrink-0 text-right text-xs text-muted">
                {share(slice.value, total)}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
