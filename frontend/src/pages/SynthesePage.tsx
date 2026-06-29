import { useQuery } from '@tanstack/react-query';
import {
  AlertTriangle,
  ArrowRight,
  CalendarClock,
  Download,
  FileClock,
  Pencil,
  Plus,
  Wallet,
} from 'lucide-react';
import { lazy, Suspense, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import {
  accountingApi,
  type CompteTresorerie,
  type Synthese,
  type SyntheseParams,
  TYPE_TRESORERIE_LABELS,
} from '@/api/accounting';
import { ExportMenu } from '@/components/ExportMenu';
import { TreasuryAccountDialog } from '@/components/TreasuryAccountDialog';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { useActiveAssociation } from '@/hooks/useActiveAssociation';
import { usePermissions } from '@/hooks/usePermissions';
import { PERMISSIONS } from '@/lib/permissions';
import { triggerDownload } from '@/lib/download';
import { formatDate, formatEUR } from '@/lib/format';
import { cn } from '@/lib/utils';

// Charts live in a lazily-loaded chunk so recharts never weighs on the main bundle.
const SyntheseCharts = lazy(() => import('@/components/charts/SyntheseCharts'));

type Preset = 'mois' | 'trimestre' | 'exercice' | 'custom';

const PRESET_LABELS: Record<Preset, string> = {
  mois: 'Mois',
  trimestre: 'Trimestre',
  exercice: 'Exercice',
  custom: 'Personnalisé',
};

function ymd(year: number, month1: number, day: number): string {
  return `${year}-${String(month1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
}

/** Period parameters for a preset (exercice → empty: the server uses the open one). */
function presetParams(preset: Preset, customFrom: string, customTo: string): SyntheseParams {
  const now = new Date();
  const year = now.getFullYear();
  if (preset === 'mois') {
    const m = now.getMonth(); // 0-based
    const last = new Date(year, m + 1, 0).getDate();
    return { date_from: ymd(year, m + 1, 1), date_to: ymd(year, m + 1, last) };
  }
  if (preset === 'trimestre') {
    const start = Math.floor(now.getMonth() / 3) * 3; // 0-based first month
    const last = new Date(year, start + 3, 0).getDate();
    return { date_from: ymd(year, start + 1, 1), date_to: ymd(year, start + 3, last) };
  }
  if (preset === 'custom') {
    return customFrom && customTo ? { date_from: customFrom, date_to: customTo } : {};
  }
  return {}; // exercice
}

function StatTile({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: string;
  hint: string;
  tone?: 'recette' | 'depense';
}) {
  const valueColor =
    tone === 'recette' ? 'text-recette' : tone === 'depense' ? 'text-depense' : 'text-ink';
  return (
    <Card className="p-5">
      <p className="text-xs font-medium uppercase tracking-wider text-faint">{label}</p>
      <p className={`tabular mt-3 text-2xl font-semibold ${valueColor}`}>{value}</p>
      <p className="mt-1 text-xs text-muted">{hint}</p>
    </Card>
  );
}

function TreasuryCard({
  compte,
  onEdit,
  releveHref,
  canExport,
}: {
  compte: CompteTresorerie;
  onEdit?: () => void;
  releveHref?: string;
  canExport: boolean;
}) {
  return (
    <Card className="flex items-center gap-4 p-4">
      <span
        className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg"
        style={{
          backgroundColor: compte.couleur ? `${compte.couleur}1a` : 'var(--color-accent-soft)',
          color: compte.couleur ?? 'var(--color-accent)',
        }}
        aria-hidden
      >
        <Wallet className="h-5 w-5" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-ink">{compte.libelle}</p>
        <p className="text-xs text-muted">{TYPE_TRESORERIE_LABELS[compte.type_tresorerie]}</p>
      </div>
      <p className="tabular shrink-0 text-base font-semibold text-ink">{formatEUR(compte.solde)}</p>
      {canExport && (
        <button
          type="button"
          onClick={() => triggerDownload(releveHref ?? '')}
          aria-label={`Relevé PDF de ${compte.libelle}`}
          className="shrink-0 rounded-md p-1.5 text-faint transition-colors hover:bg-hover hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
        >
          <Download className="h-4 w-4" />
        </button>
      )}
      {onEdit && (
        <button
          type="button"
          onClick={onEdit}
          aria-label={`Modifier ${compte.libelle}`}
          className="shrink-0 rounded-md p-1.5 text-faint transition-colors hover:bg-hover hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
        >
          <Pencil className="h-4 w-4" />
        </button>
      )}
    </Card>
  );
}

function sumSoldes(comptes: CompteTresorerie[]): number {
  return comptes.reduce((total, c) => total + Number(c.solde), 0);
}

function PeriodControl({
  preset,
  onPreset,
  customFrom,
  customTo,
  onCustomFrom,
  onCustomTo,
}: {
  preset: Preset;
  onPreset: (p: Preset) => void;
  customFrom: string;
  customTo: string;
  onCustomFrom: (v: string) => void;
  onCustomTo: (v: string) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <div
        className="inline-flex rounded-lg border border-hairline bg-surface p-0.5"
        role="group"
        aria-label="Période"
      >
        {(Object.keys(PRESET_LABELS) as Preset[]).map((p) => (
          <button
            key={p}
            type="button"
            aria-pressed={preset === p}
            onClick={() => onPreset(p)}
            className={cn(
              'rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
              preset === p ? 'bg-accent text-white' : 'text-muted hover:text-ink'
            )}
          >
            {PRESET_LABELS[p]}
          </button>
        ))}
      </div>
      {preset === 'custom' && (
        <div className="flex items-center gap-1.5">
          <input
            type="date"
            aria-label="Date de début"
            value={customFrom}
            max={customTo || undefined}
            onChange={(e) => onCustomFrom(e.target.value)}
            className="h-9 rounded-lg border border-hairline bg-surface px-2 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
          />
          <span className="text-xs text-muted">au</span>
          <input
            type="date"
            aria-label="Date de fin"
            value={customTo}
            min={customFrom || undefined}
            onChange={(e) => onCustomTo(e.target.value)}
            className="h-9 rounded-lg border border-hairline bg-surface px-2 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
          />
        </div>
      )}
    </div>
  );
}

function AlertesPanel({ synthese, associationId }: { synthese: Synthese; associationId: string }) {
  const navigate = useNavigate();
  const { brouillons, evenements_depasses, exercices_a_cloturer } = synthese.alertes;
  const hasAny =
    brouillons > 0 || evenements_depasses.length > 0 || exercices_a_cloturer.length > 0;
  if (!hasAny) return null;

  return (
    <Card className="divide-y divide-hairline p-0">
      {brouillons > 0 && (
        <AlerteRow
          icon={<FileClock className="h-4 w-4" aria-hidden />}
          tone="accent"
          text={`${brouillons} écriture${brouillons > 1 ? 's' : ''} en brouillon à valider`}
          action="Ouvrir le journal"
          onClick={() => navigate(`/asso/${associationId}/journal`)}
        />
      )}
      {exercices_a_cloturer.map((ex) => (
        <AlerteRow
          key={ex.exercice_id}
          icon={<CalendarClock className="h-4 w-4" aria-hidden />}
          tone="warning"
          text={`Exercice « ${ex.libelle} » échu le ${formatDate(ex.date_fin)} — à clôturer`}
        />
      ))}
      {evenements_depasses.map((ev) => (
        <AlerteRow
          key={ev.evenement_id}
          icon={<AlertTriangle className="h-4 w-4" aria-hidden />}
          tone="depense"
          text={`« ${ev.nom} » dépasse son budget (${formatEUR(ev.realise_depenses)} / ${formatEUR(ev.budget_depenses)})`}
          action="Voir les événements"
          onClick={() => navigate(`/asso/${associationId}/evenements`)}
        />
      ))}
    </Card>
  );
}

function AlerteRow({
  icon,
  tone,
  text,
  action,
  onClick,
}: {
  icon: React.ReactNode;
  tone: 'accent' | 'warning' | 'depense';
  text: string;
  action?: string;
  onClick?: () => void;
}) {
  const toneColor =
    tone === 'depense' ? 'text-depense' : tone === 'warning' ? 'text-warning' : 'text-accent';
  return (
    <div className="flex items-center gap-3 px-4 py-3 text-sm">
      <span className={cn('shrink-0', toneColor)}>{icon}</span>
      <span className="min-w-0 flex-1 text-ink">{text}</span>
      {action && onClick && (
        <button
          type="button"
          onClick={onClick}
          className="shrink-0 text-xs font-medium text-accent hover:text-accent-hover"
        >
          {action}
        </button>
      )}
    </div>
  );
}

function ChartsSkeleton() {
  return (
    <div className="space-y-4" aria-hidden>
      <Card className="h-64 animate-pulse bg-hover/50" />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="h-44 animate-pulse bg-hover/50" />
        <Card className="h-44 animate-pulse bg-hover/50" />
      </div>
    </div>
  );
}

export function SynthesePage() {
  const { associationId } = useParams() as { associationId: string };
  const navigate = useNavigate();
  const association = useActiveAssociation();
  const { has } = usePermissions();
  const canManage = has(PERMISSIONS.TRESORERIE_MANAGE);
  const canExport = has(PERMISSIONS.REPORT_VIEW);

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<CompteTresorerie | null>(null);
  const [preset, setPreset] = useState<Preset>('exercice');
  const [customFrom, setCustomFrom] = useState('');
  const [customTo, setCustomTo] = useState('');

  const params = useMemo(
    () => presetParams(preset, customFrom, customTo),
    [preset, customFrom, customTo]
  );

  const tresorerieQuery = useQuery({
    queryKey: ['tresorerie', associationId],
    queryFn: () => accountingApi.listTresorerie(associationId),
  });
  const comptes = tresorerieQuery.data ?? [];
  const total = sumSoldes(comptes);

  const syntheseQuery = useQuery({
    queryKey: ['synthese', associationId, params],
    queryFn: () => accountingApi.getSynthese(associationId, params),
  });
  const synthese = syntheseQuery.data;

  function openCreate() {
    setEditing(null);
    setDialogOpen(true);
  }

  function openEdit(compte: CompteTresorerie) {
    setEditing(compte);
    setDialogOpen(true);
  }

  function statValue(amount: string | undefined): string {
    if (syntheseQuery.isLoading) return '…';
    if (amount === undefined) return '—';
    return formatEUR(amount);
  }

  const resultatTone = synthese && Number(synthese.resultat.resultat) < 0 ? 'depense' : 'recette';
  const hasChartData =
    !!synthese &&
    (synthese.courbe_tresorerie.length > 0 ||
      synthese.repartition_categories.length > 0 ||
      synthese.repartition_evenements.length > 0);

  return (
    <div className="mx-auto max-w-6xl space-y-7">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold tracking-tight text-ink">
            {association?.name ?? 'Synthèse'}
          </h2>
          <p className="mt-1 text-sm text-muted">
            {synthese
              ? `Période du ${formatDate(synthese.date_from)} au ${formatDate(synthese.date_to)}`
              : 'Vue d’ensemble'}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <PeriodControl
            preset={preset}
            onPreset={setPreset}
            customFrom={customFrom}
            customTo={customTo}
            onCustomFrom={setCustomFrom}
            onCustomTo={setCustomTo}
          />
          {canExport && (
            <ExportMenu
              label="États"
              groups={[
                {
                  heading: 'États comptables',
                  items: [
                    {
                      label: 'Compte de résultat (PDF)',
                      url: accountingApi.compteResultatPdfUrl(associationId, params),
                    },
                    { label: 'Bilan (PDF)', url: accountingApi.bilanPdfUrl(associationId, params) },
                  ],
                },
              ]}
            />
          )}
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile
          label="Trésorerie"
          value={tresorerieQuery.isLoading ? '…' : formatEUR(total)}
          hint="Solde consolidé des comptes"
        />
        <StatTile
          label="Résultat"
          value={statValue(synthese?.resultat.resultat)}
          hint="Produits − charges de la période"
          tone={synthese ? resultatTone : undefined}
        />
        <StatTile
          label="Recettes"
          value={statValue(synthese?.resultat.recettes)}
          hint="Produits de la période"
          tone="recette"
        />
        <StatTile
          label="Dépenses"
          value={statValue(synthese?.resultat.depenses)}
          hint="Charges de la période"
          tone="depense"
        />
      </div>

      {synthese && <AlertesPanel synthese={synthese} associationId={associationId} />}

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-ink-soft">Comptes de trésorerie</h3>
          {canManage && (
            <Button variant="outline" size="sm" onClick={openCreate}>
              <Plus className="h-4 w-4" aria-hidden />
              Nouveau compte
            </Button>
          )}
        </div>
        {tresorerieQuery.isError ? (
          <Card className="p-5 text-sm text-muted">
            Impossible de charger les comptes de trésorerie.
          </Card>
        ) : comptes.length === 0 && !tresorerieQuery.isLoading ? (
          <Card className="p-5 text-sm text-muted">
            Aucun compte de trésorerie{canManage ? ' — créez-en un pour démarrer.' : '.'}
          </Card>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {comptes.map((compte) => (
              <TreasuryCard
                key={compte.id}
                compte={compte}
                onEdit={canManage ? () => openEdit(compte) : undefined}
                releveHref={accountingApi.relevePdfUrl(associationId, compte.id, params)}
                canExport={canExport}
              />
            ))}
          </div>
        )}
      </section>

      {syntheseQuery.isError ? (
        <Card className="p-5 text-sm text-muted">Impossible de charger la synthèse.</Card>
      ) : hasChartData ? (
        <Suspense fallback={<ChartsSkeleton />}>
          <SyntheseCharts synthese={synthese} />
        </Suspense>
      ) : synthese && !syntheseQuery.isLoading ? (
        <Card className="flex flex-col items-center gap-4 px-6 py-12 text-center">
          <div>
            <h3 className="text-base font-semibold text-ink">Aucun mouvement sur la période</h3>
            <p className="mx-auto mt-1.5 max-w-sm text-sm text-muted">
              Saisissez une recette ou une dépense : Abacus génère l’écriture comptable et met les
              soldes à jour.
            </p>
          </div>
          <Button onClick={() => navigate(`/asso/${associationId}/saisie`)}>
            Saisir une opération
            <ArrowRight className="h-4 w-4" aria-hidden />
          </Button>
        </Card>
      ) : null}

      {canManage && (
        <TreasuryAccountDialog
          associationId={associationId}
          compte={editing}
          open={dialogOpen}
          onOpenChange={setDialogOpen}
        />
      )}
    </div>
  );
}
