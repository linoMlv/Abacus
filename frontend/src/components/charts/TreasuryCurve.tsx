import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import type { CourbePoint } from '@/api/accounting';
import { formatDate, formatEUR } from '@/lib/format';

/*
 * Treasury evolution area chart. Default export so it rides the lazy `charts`
 * chunk with recharts. The hero uses it chrome-less (the number carries the
 * value); a full variant with axes is available for a standalone curve.
 */
const ACCENT = '#2563eb';
const HAIRLINE = '#e2e8f0';
const MUTED = '#64748b';
const AXIS = { fontSize: 12, fill: MUTED } as const;

const prefersReducedMotion =
  typeof window !== 'undefined' &&
  typeof window.matchMedia === 'function' &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/** Compact axis money (e.g. "1,2 k€"); full precision stays in the tooltip. */
function shortEUR(value: number): string {
  if (Math.abs(value) >= 1000) return `${(value / 1000).toLocaleString('fr-FR')} k€`;
  return `${value} €`;
}

export default function TreasuryCurve({
  points,
  showAxes = false,
}: {
  points: CourbePoint[];
  showAxes?: boolean;
}) {
  const data = points.map((p) => ({ date: p.date, solde: Number(p.solde) }));
  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={data} margin={{ top: 6, right: 6, bottom: 0, left: showAxes ? 8 : 0 }}>
        <defs>
          <linearGradient id="treso-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={ACCENT} stopOpacity={0.18} />
            <stop offset="100%" stopColor={ACCENT} stopOpacity={0} />
          </linearGradient>
        </defs>
        {showAxes ? (
          <>
            <CartesianGrid stroke={HAIRLINE} vertical={false} />
            <XAxis
              dataKey="date"
              tick={AXIS}
              tickLine={false}
              axisLine={{ stroke: HAIRLINE }}
              tickFormatter={(d: string) => formatDate(d).slice(0, 5)}
              minTickGap={24}
            />
            <YAxis
              tick={AXIS}
              tickLine={false}
              axisLine={false}
              width={56}
              tickFormatter={shortEUR}
            />
          </>
        ) : (
          <XAxis dataKey="date" hide />
        )}
        <Tooltip
          content={({ active, payload, label }) =>
            active && payload?.length ? (
              <div className="rounded-lg border border-hairline bg-surface px-3 py-2 text-xs shadow-lg shadow-ink/5">
                <p className="mb-0.5 text-muted">{formatDate(label as string)}</p>
                <p className="tabular font-semibold text-ink">
                  {formatEUR(Number(payload[0].value))}
                </p>
              </div>
            ) : null
          }
        />
        <Area
          type="monotone"
          dataKey="solde"
          stroke={ACCENT}
          strokeWidth={2}
          fill="url(#treso-fill)"
          dot={!showAxes && data.length <= 12 ? { r: 2 } : false}
          isAnimationActive={!prefersReducedMotion}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
