import { ArrowRightLeft, Undo2 } from 'lucide-react';

import type { EcritureListItem } from '@/api/accounting';
import { Card } from '@/components/ui/card';
import { formatDate, formatEUR } from '@/lib/format';
import { cn } from '@/lib/utils';

import { OperationChips } from './OperationChips';
import { StatutBadge } from './StatutBadge';
import type { JournalTableProps } from './types';

/**
 * The journal without jargon (C4): what happened, for whom, on which account and
 * how much — money in or out, coloured *and* signed (colour is never the only
 * carrier). Débit, crédit, journal codes and voucher numbers live in the
 * accounting view; nothing is hidden, only folded away.
 */
export function JournalTableSimple({
  associationId,
  rows,
  onSelect,
  selectable,
  selectedIds,
  onToggleRow,
  onToggleAll,
}: JournalTableProps) {
  const selectedSet = new Set(selectedIds);
  const allSelected = rows.length > 0 && selectedIds.length >= rows.length;

  return (
    <Card className="overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[36rem] text-sm">
          <caption className="sr-only">Journal des opérations, les plus récentes d’abord</caption>
          <thead>
            <tr className="border-b border-hairline text-left text-xs uppercase tracking-wider text-faint">
              {selectable && (
                <th scope="col" className="w-10 px-4 py-2.5">
                  <input
                    type="checkbox"
                    aria-label="Tout sélectionner"
                    className="h-4 w-4 rounded border-hairline accent-accent"
                    checked={allSelected}
                    onChange={onToggleAll}
                  />
                </th>
              )}
              <th scope="col" className="px-4 py-2.5 font-medium">
                Date
              </th>
              <th scope="col" className="px-4 py-2.5 font-medium">
                Opération
              </th>
              <th scope="col" className="px-4 py-2.5 font-medium">
                Compte
              </th>
              <th scope="col" className="px-4 py-2.5 text-right font-medium">
                Montant
              </th>
              <th scope="col" className="px-4 py-2.5 font-medium">
                Statut
              </th>
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
                <td className="whitespace-nowrap px-4 py-2.5 tabular-nums text-muted">
                  {formatDate(e.date)}
                </td>
                <td className="px-4 py-2.5">
                  <span className="text-ink">{e.libelle}</span>
                  {e.origine === 'extourne' && (
                    <span className="ml-2 inline-flex items-center gap-1 align-middle text-xs text-muted">
                      <Undo2 className="h-3.5 w-3.5" aria-hidden />
                      Annulation
                    </span>
                  )}
                  <OperationChips associationId={associationId} entry={e} />
                </td>
                <td className="whitespace-nowrap px-4 py-2.5 text-muted">
                  <CompteCell entry={e} />
                </td>
                <td className="px-4 py-2.5 text-right">
                  <MontantCell entry={e} />
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

/** Where the money sits — and, for a virement, where it went. */
function CompteCell({ entry }: { entry: EcritureListItem }) {
  if (!entry.compte_libelle) return <span className="text-faint">—</span>;
  if (!entry.compte_contrepartie_libelle) return <>{entry.compte_libelle}</>;
  return (
    <span className="inline-flex items-center gap-1.5">
      {entry.compte_libelle}
      <ArrowRightLeft className="h-3.5 w-3.5 text-faint" aria-hidden />
      {entry.compte_contrepartie_libelle}
    </span>
  );
}

/**
 * Money in (+) or out (−) of treasury, coloured to match. A virement moves nothing
 * in or out, so it stays neutral and unsigned; an entry that never touches treasury
 * falls back to its total.
 */
function MontantCell({ entry }: { entry: EcritureListItem }) {
  const mouvement = entry.montant_tresorerie === null ? null : Number(entry.montant_tresorerie);

  if (mouvement === null || mouvement === 0) {
    return <span className="font-mono tabular-nums text-ink-soft">{formatEUR(entry.montant)}</span>;
  }
  const positive = mouvement > 0;
  return (
    <span
      className={cn(
        'font-mono font-medium tabular-nums',
        positive ? 'text-recette' : 'text-depense'
      )}
    >
      {positive ? '+' : '−'}
      {formatEUR(Math.abs(mouvement))}
    </span>
  );
}
