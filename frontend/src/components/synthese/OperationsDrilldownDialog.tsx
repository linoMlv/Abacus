import { useQuery } from '@tanstack/react-query';

import { accountingApi, type JournalFilters } from '@/api/accounting';
import { StatutBadge } from '@/components/journal/StatutBadge';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog';
import { formatDate, formatEUR } from '@/lib/format';
import { cn } from '@/lib/utils';

/** A clicked donut segment, resolved to a filtered listing of its operations. */
export interface DrilldownSegment {
  /** Segment label (category, event or account name). */
  title: string;
  /** Secondary line under the title (e.g. "Dépenses · période"). */
  subtitle?: string;
  /** Segment total, shown next to the title. */
  total: number;
  /** Colours the total and amounts by their accounting nature. */
  tone?: 'recette' | 'depense' | 'neutral';
  /** Server-scoped filter selecting exactly this segment's operations. */
  filter: JournalFilters;
}

interface Props {
  associationId: string;
  segment: DrilldownSegment | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const toneText: Record<NonNullable<DrilldownSegment['tone']>, string> = {
  recette: 'text-recette',
  depense: 'text-depense',
  neutral: 'text-ink',
};

/**
 * Drill-down for a Synthèse répartition: opening it lists the entries behind one
 * donut segment. The listing is server-scoped by the segment's own filter
 * (category / event / account + the selected period) — an id from the client can
 * only ever narrow the query, never widen access.
 */
export function OperationsDrilldownDialog({ associationId, segment, open, onOpenChange }: Props) {
  const query = useQuery({
    queryKey: ['synthese-drilldown', associationId, segment?.filter],
    queryFn: () => accountingApi.listEcritures(associationId, segment!.filter),
    enabled: open && segment !== null,
  });
  const rows = query.data ?? [];
  const tone = segment?.tone ?? 'neutral';

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogTitle className="flex items-baseline justify-between gap-4 pr-6">
          <span className="truncate">{segment?.title ?? 'Opérations'}</span>
          {segment && (
            <span className={cn('shrink-0 tabular text-base font-semibold', toneText[tone])}>
              {formatEUR(segment.total)}
            </span>
          )}
        </DialogTitle>
        <DialogDescription>{segment?.subtitle ?? 'Opérations du segment'}</DialogDescription>

        <div className="mt-4 max-h-[60vh] overflow-y-auto">
          {query.isLoading ? (
            <ul className="space-y-2" aria-hidden>
              {[0, 1, 2].map((i) => (
                <li key={i} className="h-12 animate-pulse rounded-lg bg-hover" />
              ))}
            </ul>
          ) : query.isError ? (
            <p className="py-8 text-center text-sm text-muted">
              Impossible de charger les opérations.
            </p>
          ) : rows.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted">Aucune opération sur ce segment.</p>
          ) : (
            <ul className="divide-y divide-hairline">
              {rows.map((e) => (
                <li key={e.id} className="flex items-center justify-between gap-3 py-2.5">
                  <div className="min-w-0">
                    <p className="truncate text-sm text-ink">
                      {e.libelle || `Pièce ${e.numero_piece}`}
                    </p>
                    <p className="mt-0.5 flex items-center gap-1.5 text-xs text-muted">
                      <span>{formatDate(e.date)}</span>
                      <span className="text-hairline" aria-hidden>
                        ·
                      </span>
                      <span>{e.journal_code}</span>
                      {e.statut === 'brouillon' && <StatutBadge statut="brouillon" />}
                    </p>
                  </div>
                  <span className={cn('shrink-0 tabular text-sm font-medium', toneText[tone])}>
                    {formatEUR(e.montant)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
