import type { EcritureListItem } from '@/api/accounting';
import { Badge } from '@/components/ui/badge';
import { Card } from '@/components/ui/card';
import { formatDate, formatEUR } from '@/lib/format';

import { StatutBadge } from './StatutBadge';

export function JournalTable({
  rows,
  onSelect,
  selectable,
  selectedIds,
  onToggleRow,
  onToggleAll,
}: {
  rows: EcritureListItem[];
  onSelect: (id: string) => void;
  selectable: boolean;
  selectedIds: string[];
  onToggleRow: (id: string) => void;
  onToggleAll: () => void;
}) {
  const selectedSet = new Set(selectedIds);
  const allSelected = rows.length > 0 && selectedIds.length >= rows.length;
  return (
    <Card className="overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[34rem] text-sm">
          <thead>
            <tr className="border-b border-hairline text-left text-xs uppercase tracking-wider text-faint">
              {selectable && (
                <th className="w-10 px-4 py-2.5">
                  <input
                    type="checkbox"
                    aria-label="Tout sélectionner"
                    className="h-4 w-4 rounded border-hairline accent-accent"
                    checked={allSelected}
                    onChange={onToggleAll}
                  />
                </th>
              )}
              <th className="px-4 py-2.5 font-medium">Date</th>
              <th className="px-4 py-2.5 font-medium">Pièce</th>
              <th className="px-4 py-2.5 font-medium">Journal</th>
              <th className="px-4 py-2.5 font-medium">Libellé</th>
              <th className="px-4 py-2.5 text-right font-medium">Montant</th>
              <th className="px-4 py-2.5 font-medium">Statut</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((e) => (
              <tr
                key={e.id}
                onClick={() => onSelect(e.id)}
                className="cursor-pointer border-b border-hairline last:border-0 hover:bg-hover"
              >
                {selectable && (
                  <td className="px-4 py-2.5" onClick={(ev) => ev.stopPropagation()}>
                    <input
                      type="checkbox"
                      aria-label={`Sélectionner « ${e.libelle} »`}
                      className="h-4 w-4 rounded border-hairline accent-accent"
                      checked={selectedSet.has(e.id)}
                      onChange={() => onToggleRow(e.id)}
                    />
                  </td>
                )}
                <td className="whitespace-nowrap px-4 py-2.5 text-muted">{formatDate(e.date)}</td>
                <td className="px-4 py-2.5 font-mono text-xs tabular-nums text-muted">
                  {e.numero_piece}
                </td>
                <td className="px-4 py-2.5">
                  <Badge variant="neutral">{e.journal_code}</Badge>
                </td>
                <td className="px-4 py-2.5 text-ink">{e.libelle}</td>
                <td className="px-4 py-2.5 text-right font-mono tabular-nums text-ink">
                  {formatEUR(e.montant)}
                </td>
                <td className="px-4 py-2.5">
                  <StatutBadge statut={e.statut} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

/** Placeholder rows while the first page loads (avoids an empty-state flash). */
export function JournalSkeleton() {
  return (
    <Card className="overflow-hidden" aria-hidden>
      <div className="divide-y divide-hairline">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="flex items-center gap-4 px-4 py-3">
            <div className="h-3 w-20 animate-pulse rounded bg-hairline" />
            <div className="h-3 w-10 animate-pulse rounded bg-hairline" />
            <div className="h-3 flex-1 animate-pulse rounded bg-hairline" />
            <div className="h-3 w-16 animate-pulse rounded bg-hairline" />
          </div>
        ))}
      </div>
    </Card>
  );
}
