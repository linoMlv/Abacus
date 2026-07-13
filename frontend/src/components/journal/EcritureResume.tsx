import type { Compte, Ecriture } from '@/api/accounting';
import { formatEUR } from '@/lib/format';
import { cn } from '@/lib/utils';

import { OperationChips } from './OperationChips';

/**
 * An entry as the volunteer who typed it thinks of it: how much moved, in or out,
 * on which account, for what. The same facts the accounting lines state — read
 * without débit, crédit or account numbers (C4).
 */
export function EcritureResume({
  associationId,
  entry,
  comptes,
}: {
  associationId: string;
  entry: Ecriture;
  comptes: Compte[];
}) {
  const byId = new Map(comptes.map((c) => [c.id, c]));
  const tresorerie = entry.lignes.filter((l) => byId.get(l.compte_id)?.classe === 5);
  const mouvement = tresorerie.reduce((sum, l) => sum + Number(l.debit) - Number(l.credit), 0);
  const total = entry.lignes.reduce((sum, l) => sum + Number(l.debit), 0);

  const entree = tresorerie.find((l) => Number(l.debit) > 0);
  const sortie = tresorerie.find((l) => Number(l.credit) > 0);
  const isVirement = !!entree && !!sortie;

  return (
    <dl className="space-y-3 text-sm">
      <div className="flex items-baseline justify-between gap-3">
        <dt className="text-muted">Montant</dt>
        <dd
          className={cn(
            'font-mono text-lg font-semibold tabular-nums',
            isVirement || mouvement === 0
              ? 'text-ink'
              : mouvement > 0
                ? 'text-recette'
                : 'text-depense'
          )}
        >
          {isVirement || mouvement === 0
            ? formatEUR(total)
            : `${mouvement > 0 ? '+' : '−'}${formatEUR(Math.abs(mouvement))}`}
        </dd>
      </div>

      {isVirement ? (
        <>
          <Row label="Depuis" value={byId.get(sortie.compte_id)?.libelle ?? '—'} />
          <Row label="Vers" value={byId.get(entree.compte_id)?.libelle ?? '—'} />
        </>
      ) : (
        <Row
          label={mouvement > 0 ? 'Reçu sur' : 'Payé depuis'}
          value={
            byId.get((entree ?? sortie)?.compte_id ?? '')?.libelle ?? 'Aucun compte de trésorerie'
          }
        />
      )}

      {(entry.categorie_id || entry.tiers_id || entry.evenement_id) && (
        <div className="flex items-baseline justify-between gap-3">
          <dt className="text-muted">Rattachée à</dt>
          <dd>
            <OperationChips associationId={associationId} entry={entry} />
          </dd>
        </div>
      )}
    </dl>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className="text-muted">{label}</dt>
      <dd className="text-right text-ink">{value}</dd>
    </div>
  );
}
