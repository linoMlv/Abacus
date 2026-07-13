import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useParams } from 'react-router-dom';

import { accountingApi } from '@/api/accounting';
import { ExerciceSelect } from '@/components/comptes/ExerciceSelect';
import { Alert } from '@/components/ui/alert';
import { Card } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import { formatAmount, formatDate } from '@/lib/format';

/**
 * Ledger of a single account: its validated movements in date order with the
 * running balance. Only accounts that carry movements are offered — an empty
 * ledger is a dead end, and the balance already tells us which ones move.
 */
export function GrandLivreTab() {
  const { associationId } = useParams() as { associationId: string };
  const [compteId, setCompteId] = useState('');
  const [exerciceId, setExerciceId] = useState('');

  const balanceQuery = useQuery({
    queryKey: ['balance', associationId, exerciceId || 'tous'],
    queryFn: () => accountingApi.getBalance(associationId, exerciceId || undefined),
  });
  const comptes = balanceQuery.data ?? [];
  const selected = comptes.find((c) => c.compte_id === compteId) ?? comptes[0];

  const ligneQuery = useQuery({
    queryKey: ['grand-livre', associationId, selected?.compte_id, exerciceId || 'tous'],
    queryFn: () =>
      accountingApi.getGrandLivre(associationId, selected!.compte_id, exerciceId || undefined),
    enabled: !!selected,
  });
  const lignes = ligneQuery.data ?? [];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-4">
        <div className="min-w-64 flex-1">
          <Label htmlFor="gl-compte">Compte</Label>
          <Select
            id="gl-compte"
            className="mt-1.5"
            value={selected?.compte_id ?? ''}
            onChange={(e) => setCompteId(e.target.value)}
            disabled={comptes.length === 0}
          >
            {comptes.length === 0 && <option value="">Aucun compte mouvementé</option>}
            {comptes.map((c) => (
              <option key={c.compte_id} value={c.compte_id}>
                {c.numero} — {c.libelle}
              </option>
            ))}
          </Select>
        </div>
        <ExerciceSelect id="gl-exercice" value={exerciceId} onChange={setExerciceId} />
      </div>

      {(balanceQuery.isError || ligneQuery.isError) && (
        <Alert>Impossible de charger le grand livre.</Alert>
      )}

      <Card className="overflow-hidden">
        {balanceQuery.isLoading || ligneQuery.isLoading ? (
          <p className="px-4 py-6 text-sm text-muted">Chargement…</p>
        ) : lignes.length === 0 ? (
          <p className="px-4 py-6 text-sm text-muted">
            Aucun mouvement validé sur ce compte pour la période choisie.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[42rem] text-sm">
              <caption className="sr-only">
                Grand livre du compte {selected?.numero} {selected?.libelle}
              </caption>
              <thead>
                <tr className="border-b border-hairline text-xs uppercase tracking-wide text-muted">
                  <th scope="col" className="px-4 py-2.5 text-left font-medium">
                    Date
                  </th>
                  <th scope="col" className="px-4 py-2.5 text-left font-medium">
                    Pièce
                  </th>
                  <th scope="col" className="px-4 py-2.5 text-left font-medium">
                    Libellé
                  </th>
                  <th scope="col" className="px-4 py-2.5 text-right font-medium">
                    Débit (€)
                  </th>
                  <th scope="col" className="px-4 py-2.5 text-right font-medium">
                    Crédit (€)
                  </th>
                  <th scope="col" className="px-4 py-2.5 text-right font-medium">
                    Solde (€)
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-hairline">
                {lignes.map((ligne, index) => (
                  <tr key={`${ligne.ecriture_id}-${index}`} className="hover:bg-hover">
                    <td className="whitespace-nowrap px-4 py-2.5 tabular-nums text-ink-soft">
                      {formatDate(ligne.date)}
                    </td>
                    <td className="px-4 py-2.5 font-mono text-xs tabular-nums text-faint">
                      {ligne.numero_piece}
                    </td>
                    <td className="px-4 py-2.5 text-ink">{ligne.libelle}</td>
                    <td className="px-4 py-2.5 text-right font-mono tabular-nums text-ink-soft">
                      {formatAmount(ligne.debit)}
                    </td>
                    <td className="px-4 py-2.5 text-right font-mono tabular-nums text-ink-soft">
                      {formatAmount(ligne.credit)}
                    </td>
                    <td className="px-4 py-2.5 text-right font-mono tabular-nums font-medium text-ink">
                      {formatAmount(ligne.solde)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
