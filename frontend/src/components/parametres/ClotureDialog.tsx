import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';

import { accountingApi, type Exercice } from '@/api/accounting';
import { apiErrorMessage } from '@/api/client';
import { Alert } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { formatEUR } from '@/lib/format';

/** Round to cents to compare affectation amounts without float drift. */
function cents(value: string): number {
  return Math.round((Number(value) || 0) * 100);
}

/**
 * Closing wizard: shows the exercice result (from the synthèse of its period) and
 * lets the treasurer split it between report à nouveau (110/119) and reserves
 * (106). The server re-computes and enforces the split against the true result.
 */
export function ClotureDialog({
  associationId,
  exercice,
  onOpenChange,
}: {
  associationId: string;
  exercice: Exercice | null;
  onOpenChange: (open: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const open = exercice !== null;

  const syntheseQuery = useQuery({
    queryKey: ['synthese', associationId, exercice?.date_debut, exercice?.date_fin],
    queryFn: () =>
      accountingApi.getSynthese(associationId, {
        date_from: exercice!.date_debut,
        date_to: exercice!.date_fin,
      }),
    enabled: open,
  });

  const resultat = Number(syntheseQuery.data?.resultat.resultat ?? '0');
  const aAffecter = Math.abs(resultat);
  const excedent = resultat >= 0;

  const [report, setReport] = useState('0');
  const [reserves, setReserves] = useState('0');

  // Default the whole result to report à nouveau once the amount is known.
  useEffect(() => {
    if (open && syntheseQuery.data) {
      setReport(aAffecter.toFixed(2));
      setReserves('0');
    }
  }, [open, syntheseQuery.data, aAffecter]);

  const cloture = useMutation({
    mutationFn: () =>
      accountingApi.cloturerExercice(associationId, exercice!.id, {
        report_a_nouveau: report,
        reserves: reserves,
      }),
    onSuccess: () => {
      // The result moved, a new year opened and entries locked: refresh broadly.
      for (const key of ['exercices', 'synthese', 'tresorerie', 'ecritures']) {
        queryClient.invalidateQueries({ queryKey: [key, associationId] });
      }
      onOpenChange(false);
    },
  });

  const affecte = cents(report) + cents(reserves);
  const equilibre = affecte === Math.round(aAffecter * 100);

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onOpenChange(false)}>
      <DialogContent className="max-w-md">
        <DialogTitle>Clôturer l’exercice {exercice?.libelle}</DialogTitle>
        <DialogDescription>
          La clôture est définitive : elle détermine le résultat, génère le report à nouveau dans
          l’exercice suivant et verrouille les écritures de la période.
        </DialogDescription>

        {syntheseQuery.isLoading ? (
          <p className="mt-4 text-sm text-muted">Calcul du résultat…</p>
        ) : syntheseQuery.isError ? (
          <Alert className="mt-4">Impossible de calculer le résultat de l’exercice.</Alert>
        ) : (
          <form
            className="mt-4 space-y-4"
            onSubmit={(e) => {
              e.preventDefault();
              if (equilibre) cloture.mutate();
            }}
          >
            <div className="rounded-lg border border-hairline bg-hover px-3.5 py-3">
              <p className="text-xs text-muted">Résultat de l’exercice</p>
              <p
                className={`text-lg font-semibold tabular-nums ${excedent ? 'text-recette' : 'text-depense'}`}
              >
                {formatEUR(resultat)} — {excedent ? 'excédent' : 'déficit'}
              </p>
            </div>

            {aAffecter === 0 ? (
              <p className="text-sm text-muted">
                Résultat nul : rien à affecter. La clôture reporte simplement les soldes.
              </p>
            ) : (
              <>
                <p className="text-sm text-ink-soft">
                  Affectez le résultat entre report à nouveau
                  {excedent ? ' (110)' : ' (119)'} et réserves (106).
                </p>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label htmlFor="cl-report">Report à nouveau</Label>
                    <Input
                      id="cl-report"
                      type="number"
                      step="0.01"
                      min="0"
                      value={report}
                      onChange={(e) => setReport(e.target.value)}
                    />
                  </div>
                  <div>
                    <Label htmlFor="cl-reserves">Réserves</Label>
                    <Input
                      id="cl-reserves"
                      type="number"
                      step="0.01"
                      min="0"
                      value={reserves}
                      onChange={(e) => setReserves(e.target.value)}
                    />
                  </div>
                </div>
                {!equilibre && (
                  <p className="text-xs text-depense">
                    La somme affectée doit égaler {formatEUR(aAffecter)}.
                  </p>
                )}
              </>
            )}

            {cloture.isError && <Alert>{apiErrorMessage(cloture, 'Clôture impossible.')}</Alert>}
            <div className="flex justify-end gap-2 border-t border-hairline pt-4">
              <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
                Annuler
              </Button>
              <Button type="submit" variant="accent" disabled={cloture.isPending || !equilibre}>
                {cloture.isPending ? 'Clôture…' : 'Clôturer l’exercice'}
              </Button>
            </div>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
