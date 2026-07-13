import type { EcritureListItem } from '@/api/accounting';
import { Badge } from '@/components/ui/badge';
import { Card } from '@/components/ui/card';
import { formatAmount, formatDate } from '@/lib/format';

import { StatutBadge } from './StatutBadge';
import { ORIGINE_LABELS, type JournalTableProps } from './types';

/**
 * The accountant's reading of the same journal: voucher number, journal code,
 * origine — and each entry's own lines underneath, account by account, débit and
 * crédit. What a contre-passation reverses is visible here, not merely implied.
 */
export function JournalTableAccounting({
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
        <table className="w-full min-w-[48rem] text-sm">
          <caption className="sr-only">
            Journal comptable : écritures et leurs lignes en débit / crédit
          </caption>
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
                Pièce
              </th>
              <th scope="col" className="px-4 py-2.5 font-medium">
                Journal
              </th>
              <th scope="col" className="px-4 py-2.5 font-medium">
                Compte / libellé
              </th>
              <th scope="col" className="px-4 py-2.5 text-right font-medium">
                Débit
              </th>
              <th scope="col" className="px-4 py-2.5 text-right font-medium">
                Crédit
              </th>
              <th scope="col" className="px-4 py-2.5 font-medium">
                Statut
              </th>
            </tr>
          </thead>
          {rows.map((e) => (
            <tbody key={e.id} className="border-b border-hairline last:border-0">
              <tr onClick={() => onSelect(e.id)} className="cursor-pointer hover:bg-hover">
                {selectable && (
                  <td className="px-4 pt-2.5" onClick={(ev) => ev.stopPropagation()}>
                    <input
                      type="checkbox"
                      aria-label={`Sélectionner « ${e.libelle} »`}
                      className="h-4 w-4 rounded border-hairline accent-accent"
                      checked={selectedSet.has(e.id)}
                      onChange={() => onToggleRow(e.id)}
                    />
                  </td>
                )}
                <td className="whitespace-nowrap px-4 pt-2.5 tabular-nums text-muted">
                  {formatDate(e.date)}
                </td>
                <td className="px-4 pt-2.5 font-mono text-xs tabular-nums text-muted">
                  {e.numero_piece}
                </td>
                <td className="px-4 pt-2.5">
                  <Badge variant="neutral">{e.journal_code}</Badge>
                </td>
                <td className="px-4 pt-2.5 text-ink">
                  {e.libelle}
                  <OrigineTag entry={e} />
                </td>
                <td className="px-4 pt-2.5 text-right font-mono tabular-nums text-ink-soft">
                  {formatAmount(e.montant)}
                </td>
                <td className="px-4 pt-2.5 text-right font-mono tabular-nums text-ink-soft">
                  {formatAmount(e.montant)}
                </td>
                <td className="px-4 pt-2.5">
                  <StatutBadge statut={e.statut} />
                </td>
              </tr>
              {e.lignes.map((ligne, index) => (
                <tr
                  key={`${e.id}-${index}`}
                  onClick={() => onSelect(e.id)}
                  className="cursor-pointer text-xs hover:bg-hover"
                >
                  {selectable && <td className="px-4" />}
                  <td className="px-4" />
                  <td className="px-4" />
                  <td className="px-4" />
                  <td className="px-4 py-1 pl-8 text-muted">
                    <span className="mr-2 font-mono tabular-nums text-faint">
                      {ligne.compte_numero}
                    </span>
                    {ligne.compte_libelle}
                  </td>
                  <td className="px-4 py-1 text-right font-mono tabular-nums text-muted">
                    {Number(ligne.debit) > 0 ? formatAmount(ligne.debit) : ''}
                  </td>
                  <td className="px-4 py-1 text-right font-mono tabular-nums text-muted">
                    {Number(ligne.credit) > 0 ? formatAmount(ligne.credit) : ''}
                  </td>
                  <td className="px-4" />
                </tr>
              ))}
              <tr aria-hidden>
                <td className="pb-1.5" colSpan={selectable ? 8 : 7} />
              </tr>
            </tbody>
          ))}
        </table>
      </div>
    </Card>
  );
}

/** Why this entry exists, when it was not typed in by hand. */
function OrigineTag({ entry }: { entry: EcritureListItem }) {
  if (entry.origine === 'saisie_simple' || entry.origine === 'manuelle') return null;
  return (
    <span className="ml-2 rounded border border-hairline px-1.5 py-0.5 text-xs text-muted">
      {ORIGINE_LABELS[entry.origine]}
    </span>
  );
}
