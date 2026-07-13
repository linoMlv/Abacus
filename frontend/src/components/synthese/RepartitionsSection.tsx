import { useMemo, useState } from 'react';

import type {
  CompteTresorerie,
  JournalFilters,
  RepartitionCategorie,
  RepartitionEvenement,
  RepartitionTresorerie,
  TypeOperation,
} from '@/api/accounting';
import DonutRepartition from '@/components/charts/DonutRepartition';
import { Card } from '@/components/ui/card';
import { type DonutSlice, type SliceInput, toSlices } from '@/lib/chartColors';
import { formatDate } from '@/lib/format';
import { cn } from '@/lib/utils';

import { type DrilldownSegment, OperationsDrilldownDialog } from './OperationsDrilldownDialog';

type Mode = 'categories' | 'evenements' | 'tresorerie';
type Facet = 'categorie_id' | 'evenement_id' | 'compte_id';

const MODE_LABELS: Record<Mode, string> = {
  categories: 'Catégories',
  evenements: 'Événements',
  tresorerie: 'Trésorerie',
};
const MODE_ORDER: Mode[] = ['categories', 'evenements', 'tresorerie'];

/** One donut within a mode: a labelled répartition that drills into its operations. */
interface Panel {
  key: string;
  title: string;
  tone: DrilldownSegment['tone'];
  facet: Facet;
  /** Narrows the drill-down to one nature (used where a facet mixes both, e.g. events). */
  typeOp?: TypeOperation;
  /** Spans both columns (the treasury solde donut sits under its dépenses/recettes pair). */
  fullWidth?: boolean;
  slices: DonutSlice[];
}

interface Props {
  associationId: string;
  repartitionCategories: RepartitionCategorie[];
  repartitionEvenements: RepartitionEvenement[];
  repartitionTresorerie: RepartitionTresorerie[];
  comptes: CompteTresorerie[];
  dateFrom: string;
  dateTo: string;
}

/**
 * The Synthèse répartitions. A segmented switch picks one of three modes; each
 * lays its donuts out for a global read: **Catégories** and **Événements** show
 * Dépenses and Recettes side by side, **Trésorerie** shows the balance split by
 * account. Clicking a slice — or its legend entry — drills into that segment's
 * operations. Depends on recharts, so it rides the lazy charts chunk.
 */
export function RepartitionsSection({
  associationId,
  repartitionCategories,
  repartitionEvenements,
  repartitionTresorerie,
  comptes,
  dateFrom,
  dateTo,
}: Props) {
  const panelsByMode = useMemo<Record<Mode, Panel[]>>(() => {
    const cat = (sens: 'recette' | 'depense'): SliceInput[] =>
      repartitionCategories
        .filter((c) => c.sens === sens)
        .map((c) => ({ id: c.categorie_id, label: c.libelle, value: Number(c.montant) }));
    const evt = (pick: (e: RepartitionEvenement) => string): SliceInput[] =>
      repartitionEvenements.map((e) => ({
        id: e.evenement_id,
        label: e.nom,
        value: Number(pick(e)),
      }));

    // Paired modes keep both donuts even when one side is empty (it renders as a
    // grey 0 € ring) so the two-column layout stays coherent.
    return {
      categories: [
        {
          key: 'dep',
          title: 'Dépenses',
          tone: 'depense',
          facet: 'categorie_id',
          slices: toSlices(cat('depense')),
        },
        {
          key: 'rec',
          title: 'Recettes',
          tone: 'recette',
          facet: 'categorie_id',
          slices: toSlices(cat('recette')),
        },
      ],
      evenements: [
        {
          key: 'dep',
          title: 'Dépenses',
          tone: 'depense',
          facet: 'evenement_id',
          typeOp: 'depense',
          slices: toSlices(evt((e) => e.depenses)),
        },
        {
          key: 'rec',
          title: 'Recettes',
          tone: 'recette',
          facet: 'evenement_id',
          typeOp: 'recette',
          slices: toSlices(evt((e) => e.recettes)),
        },
      ],
      tresorerie: [
        {
          key: 'dep',
          title: 'Dépenses',
          tone: 'depense',
          facet: 'compte_id',
          typeOp: 'depense',
          slices: toSlices(
            repartitionTresorerie.map((t) => ({
              id: t.compte_id,
              label: t.libelle,
              value: Number(t.depenses),
            }))
          ),
        },
        {
          key: 'rec',
          title: 'Recettes',
          tone: 'recette',
          facet: 'compte_id',
          typeOp: 'recette',
          slices: toSlices(
            repartitionTresorerie.map((t) => ({
              id: t.compte_id,
              label: t.libelle,
              value: Number(t.recettes),
            }))
          ),
        },
        {
          key: 'solde',
          title: 'Solde',
          tone: 'neutral',
          facet: 'compte_id',
          fullWidth: true,
          slices: toSlices(
            comptes.map((c) => ({ id: c.id, label: c.libelle, value: Number(c.solde) }))
          ),
        },
      ],
    };
  }, [repartitionCategories, repartitionEvenements, repartitionTresorerie, comptes]);

  const available = MODE_ORDER.filter((m) => panelsByMode[m].some((p) => p.slices.length > 0));
  const [mode, setMode] = useState<Mode>('categories');
  const activeMode = available.includes(mode) ? mode : available[0];

  const [segment, setSegment] = useState<DrilldownSegment | null>(null);
  const [open, setOpen] = useState(false);

  if (available.length === 0 || !activeMode) return null;

  const panels = panelsByMode[activeMode];

  function drill(panel: Panel, slice: DonutSlice) {
    const filter: JournalFilters = {};
    filter[panel.facet] = slice.ids;
    if (panel.typeOp) filter.type_operation = [panel.typeOp];
    filter.date_from = dateFrom;
    filter.date_to = dateTo;
    setSegment({
      title: slice.label,
      subtitle: `${panel.title} · ${formatDate(dateFrom)} – ${formatDate(dateTo)}`,
      total: slice.value,
      tone: panel.tone,
      filter,
    });
    setOpen(true);
  }

  return (
    <Card className="p-5">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-ink-soft">Répartitions</h3>
        <div className="inline-flex rounded-lg bg-hover p-0.5" role="group" aria-label="Vue">
          {available.map((m) => {
            const active = m === activeMode;
            return (
              <button
                key={m}
                type="button"
                onClick={() => setMode(m)}
                aria-pressed={active}
                className={cn(
                  'rounded-md px-2.5 py-1 text-xs font-medium transition-colors',
                  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent',
                  active
                    ? 'bg-surface text-ink shadow-sm shadow-ink/5'
                    : 'text-muted hover:text-ink'
                )}
              >
                {MODE_LABELS[m]}
              </button>
            );
          })}
        </div>
      </div>

      <div className="grid gap-8 md:grid-cols-2">
        {panels.map((panel) => {
          const total = panel.slices.reduce((sum, s) => sum + s.value, 0);
          return (
            <div
              key={panel.key}
              role="group"
              aria-label={panel.title}
              className={cn('min-w-0', panel.fullWidth && 'md:col-span-2')}
            >
              <div className="mb-3 flex items-center gap-1.5">
                <span
                  className={cn(
                    'h-1.5 w-1.5 rounded-full',
                    panel.tone === 'recette'
                      ? 'bg-recette'
                      : panel.tone === 'depense'
                        ? 'bg-depense'
                        : 'bg-accent'
                  )}
                  aria-hidden
                />
                <h4 className="text-xs font-semibold uppercase tracking-wide text-ink-soft">
                  {panel.title}
                </h4>
              </div>
              <DonutRepartition
                slices={panel.slices}
                total={total}
                centerLabel={panel.title}
                onSelect={(slice) => drill(panel, slice)}
                emptyHint="Aucune entrée sur la période."
              />
            </div>
          );
        })}
      </div>

      <OperationsDrilldownDialog
        associationId={associationId}
        segment={segment}
        open={open}
        onOpenChange={setOpen}
      />
    </Card>
  );
}
