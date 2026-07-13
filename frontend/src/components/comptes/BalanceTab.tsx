import { useQuery } from '@tanstack/react-query';
import { Check, TriangleAlert } from 'lucide-react';
import { useState } from 'react';
import { useParams } from 'react-router-dom';

import { accountingApi } from '@/api/accounting';
import { ExerciceSelect } from '@/components/comptes/ExerciceSelect';
import { Alert } from '@/components/ui/alert';
import { Card } from '@/components/ui/card';
import { cents, formatAmount } from '@/lib/format';

/**
 * Trial balance: every account carrying validated movements, its débit/crédit
 * totals and the resulting solde. Débit and crédit must always add up to the same
 * total — the double-entry invariant — so the footer states it plainly instead of
 * leaving the reader to compare two numbers.
 */
export function BalanceTab() {
  const { associationId } = useParams() as { associationId: string };
  const [exerciceId, setExerciceId] = useState('');

  const query = useQuery({
    queryKey: ['balance', associationId, exerciceId || 'tous'],
    queryFn: () => accountingApi.getBalance(associationId, exerciceId || undefined),
  });
  const lignes = query.data ?? [];

  const totalDebit = lignes.reduce((sum, l) => sum + cents(l.total_debit), 0);
  const totalCredit = lignes.reduce((sum, l) => sum + cents(l.total_credit), 0);
  const equilibree = totalDebit === totalCredit;

  return (
    <div className="space-y-4">
      <ExerciceSelect id="balance-exercice" value={exerciceId} onChange={setExerciceId} />

      {query.isError && <Alert>Impossible de charger la balance.</Alert>}

      <Card className="overflow-hidden">
        {query.isLoading ? (
          <p className="px-4 py-6 text-sm text-muted">Chargement…</p>
        ) : lignes.length === 0 ? (
          <p className="px-4 py-6 text-sm text-muted">
            Aucun mouvement validé sur cette période : la balance est vide.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[36rem] text-sm">
              <caption className="sr-only">
                Balance des comptes : totaux débit, crédit et solde par compte
              </caption>
              <thead>
                <tr className="border-b border-hairline text-xs uppercase tracking-wide text-muted">
                  <th scope="col" className="px-4 py-2.5 text-left font-medium">
                    Compte
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
                {lignes.map((ligne) => (
                  <tr key={ligne.compte_id} className="hover:bg-hover">
                    <td className="px-4 py-2.5">
                      <span className="mr-2 font-mono text-xs tabular-nums text-faint">
                        {ligne.numero}
                      </span>
                      <span className="text-ink">{ligne.libelle}</span>
                    </td>
                    <td className="px-4 py-2.5 text-right font-mono tabular-nums text-ink-soft">
                      {formatAmount(ligne.total_debit)}
                    </td>
                    <td className="px-4 py-2.5 text-right font-mono tabular-nums text-ink-soft">
                      {formatAmount(ligne.total_credit)}
                    </td>
                    <td className="px-4 py-2.5 text-right font-mono tabular-nums font-medium text-ink">
                      {formatAmount(ligne.solde)}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t-2 border-hairline bg-subtle font-medium">
                  <td className="px-4 py-2.5 text-ink">Totaux</td>
                  <td className="px-4 py-2.5 text-right font-mono tabular-nums text-ink">
                    {formatAmount(totalDebit / 100)}
                  </td>
                  <td className="px-4 py-2.5 text-right font-mono tabular-nums text-ink">
                    {formatAmount(totalCredit / 100)}
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    <span
                      className={`inline-flex items-center gap-1 text-xs ${
                        equilibree ? 'text-recette' : 'text-depense'
                      }`}
                    >
                      {equilibree ? (
                        <Check className="h-3.5 w-3.5" aria-hidden />
                      ) : (
                        <TriangleAlert className="h-3.5 w-3.5" aria-hidden />
                      )}
                      {equilibree ? 'Équilibrée' : 'Déséquilibrée'}
                    </span>
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
