import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  Cell,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import type { Synthese } from '@/api/accounting';
import { Card } from '@/components/ui/card';
import { formatDate, formatEUR } from '@/lib/format';

/*
 * Charts for the Synthèse page. Isolated in its own module so recharts (a heavy
 * dependency) is code-split into a separate chunk, lazily loaded only here — it
 * never weighs on the app's main bundle. Colors mirror the design tokens.
 */
const ACCENT = '#2563eb';
const RECETTE = '#047857';
const DEPENSE = '#dc2626';
const HAIRLINE = '#e2e8f0';
const MUTED = '#64748b';

const AXIS = { fontSize: 12, fill: MUTED } as const;

/** Compact axis money (e.g. "1,2 k€"), full precision stays in the tooltip. */
function shortEUR(value: number): string {
  if (Math.abs(value) >= 1000) return `${(value / 1000).toLocaleString('fr-FR')} k€`;
  return `${value} €`;
}

function ChartCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card className="p-5">
      <h3 className="mb-4 text-sm font-semibold text-ink-soft">{title}</h3>
      {children}
    </Card>
  );
}

function TooltipBox({ label, value }: { label?: string; value: number }) {
  return (
    <div className="rounded-lg border border-hairline bg-surface px-3 py-2 text-xs shadow-lg shadow-ink/5">
      {label && <p className="mb-0.5 text-muted">{label}</p>}
      <p className="tabular font-semibold text-ink">{formatEUR(value)}</p>
    </div>
  );
}

function TresorerieCurve({ synthese }: { synthese: Synthese }) {
  const data = synthese.courbe_tresorerie.map((p) => ({
    date: p.date,
    solde: Number(p.solde),
  }));
  return (
    <ChartCard title="Évolution de la trésorerie">
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 8 }}>
            <defs>
              <linearGradient id="treso-fill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={ACCENT} stopOpacity={0.18} />
                <stop offset="100%" stopColor={ACCENT} stopOpacity={0} />
              </linearGradient>
            </defs>
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
            <Tooltip
              content={({ active, payload, label }) =>
                active && payload?.length ? (
                  <TooltipBox
                    label={formatDate(label as string)}
                    value={Number(payload[0].value)}
                  />
                ) : null
              }
            />
            <Area
              type="monotone"
              dataKey="solde"
              stroke={ACCENT}
              strokeWidth={2}
              fill="url(#treso-fill)"
              dot={data.length <= 12}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </ChartCard>
  );
}

function RepartitionCategories({ synthese }: { synthese: Synthese }) {
  const data = synthese.repartition_categories.map((c) => ({
    name: c.libelle,
    montant: Number(c.montant),
    sens: c.sens,
  }));
  // Height grows with the number of bars so labels stay legible.
  const height = Math.max(160, data.length * 36 + 16);
  return (
    <ChartCard title="Répartition par catégorie">
      <div style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            layout="vertical"
            margin={{ top: 0, right: 12, bottom: 0, left: 8 }}
          >
            <CartesianGrid stroke={HAIRLINE} horizontal={false} />
            <XAxis
              type="number"
              tick={AXIS}
              tickLine={false}
              axisLine={false}
              tickFormatter={shortEUR}
            />
            <YAxis
              type="category"
              dataKey="name"
              tick={AXIS}
              tickLine={false}
              axisLine={false}
              width={120}
            />
            <Tooltip
              cursor={{ fill: HAIRLINE, fillOpacity: 0.4 }}
              content={({ active, payload }) =>
                active && payload?.length ? (
                  <TooltipBox label={payload[0].payload.name} value={Number(payload[0].value)} />
                ) : null
              }
            />
            <Bar dataKey="montant" radius={[0, 4, 4, 0]}>
              {data.map((d) => (
                <Cell key={d.name} fill={d.sens === 'recette' ? RECETTE : DEPENSE} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </ChartCard>
  );
}

function RepartitionEvenements({ synthese }: { synthese: Synthese }) {
  const data = synthese.repartition_evenements.map((e) => ({
    name: e.nom,
    resultat: Number(e.resultat),
    couleur: e.couleur,
  }));
  const height = Math.max(160, data.length * 36 + 16);
  return (
    <ChartCard title="Résultat par événement">
      <div style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            layout="vertical"
            margin={{ top: 0, right: 12, bottom: 0, left: 8 }}
          >
            <CartesianGrid stroke={HAIRLINE} horizontal={false} />
            <XAxis
              type="number"
              tick={AXIS}
              tickLine={false}
              axisLine={false}
              tickFormatter={shortEUR}
            />
            <YAxis
              type="category"
              dataKey="name"
              tick={AXIS}
              tickLine={false}
              axisLine={false}
              width={120}
            />
            <Tooltip
              cursor={{ fill: HAIRLINE, fillOpacity: 0.4 }}
              content={({ active, payload }) =>
                active && payload?.length ? (
                  <TooltipBox label={payload[0].payload.name} value={Number(payload[0].value)} />
                ) : null
              }
            />
            <Bar dataKey="resultat" radius={[0, 4, 4, 0]}>
              {data.map((d) => (
                <Cell key={d.name} fill={d.couleur ?? (d.resultat < 0 ? DEPENSE : RECETTE)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </ChartCard>
  );
}

/**
 * All Synthèse charts. Default export so it can be `React.lazy`-loaded, keeping
 * recharts out of the main bundle. Each sub-chart renders only when it has data.
 */
export default function SyntheseCharts({ synthese }: { synthese: Synthese }) {
  const hasCurve = synthese.courbe_tresorerie.length > 0;
  const hasCategories = synthese.repartition_categories.length > 0;
  const hasEvenements = synthese.repartition_evenements.length > 0;

  return (
    <div className="space-y-4">
      {hasCurve && <TresorerieCurve synthese={synthese} />}
      {(hasCategories || hasEvenements) && (
        <div className="grid gap-4 lg:grid-cols-2">
          {hasCategories && <RepartitionCategories synthese={synthese} />}
          {hasEvenements && <RepartitionEvenements synthese={synthese} />}
        </div>
      )}
    </div>
  );
}
