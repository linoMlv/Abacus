import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, Check, FileSpreadsheet, FileText } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';

import { accountingApi } from '@/api/accounting';
import { type Budget, budgetApi, type LigneBudget } from '@/api/budget';
import { apiErrorMessage } from '@/api/client';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { usePermissions } from '@/hooks/usePermissions';
import { triggerDownload } from '@/lib/download';
import { cents, formatEUR } from '@/lib/format';
import { PERMISSIONS } from '@/lib/permissions';
import { cn } from '@/lib/utils';

type Montants = Record<string, string>;

/** Local prévu inputs seeded from the budget (blank when zero, for a cleaner grid). */
function seedMontants(budget: Budget): Montants {
  return Object.fromEntries(
    budget.lignes.map((l) => [l.categorie_id, cents(l.montant_prevu) === 0 ? '' : l.montant_prevu])
  );
}

function sum(lignes: LigneBudget[], value: (l: LigneBudget) => number): number {
  return lignes.reduce((acc, l) => acc + value(l), 0);
}

/** Écart cell: réalisé − prévu, coloured with an icon (never colour alone). */
function EcartCell({ sens, ecart }: { sens: LigneBudget['sens']; ecart: number }) {
  const over = sens === 'depense' && ecart > 0; // spent past the budget
  const under = sens === 'recette' && ecart < 0; // received less than planned
  return (
    <span
      className={cn(
        'inline-flex items-center justify-end gap-1 tabular-nums',
        over ? 'text-depense' : under ? 'text-warning' : 'text-muted'
      )}
    >
      {over && <AlertTriangle className="h-3.5 w-3.5" aria-hidden />}
      {ecart > 0 ? '+' : ''}
      {formatEUR(ecart)}
    </span>
  );
}

export function BudgetPage() {
  const { associationId } = useParams() as { associationId: string };
  const queryClient = useQueryClient();
  const { has } = usePermissions();
  const canManage = has(PERMISSIONS.BUDGET_MANAGE);

  const [exerciceId, setExerciceId] = useState('');
  const [montants, setMontants] = useState<Montants>({});
  const [saved, setSaved] = useState(false);

  const exercicesQuery = useQuery({
    queryKey: ['exercices', associationId],
    queryFn: () => accountingApi.listExercices(associationId),
  });
  const budgetQuery = useQuery({
    queryKey: ['budget', associationId, exerciceId],
    queryFn: () => budgetApi.getBudget(associationId, exerciceId || undefined),
  });
  const budget = budgetQuery.data;

  // Reset the editable inputs whenever a fresh budget arrives (load or after save).
  useEffect(() => {
    if (budget) setMontants(seedMontants(budget));
  }, [budget]);

  const saveMutation = useMutation({
    mutationFn: () =>
      budgetApi.saveBudget(associationId, {
        exercice_id: budget!.exercice_id,
        lignes: budget!.lignes.map((l) => ({
          categorie_id: l.categorie_id,
          montant_prevu: montants[l.categorie_id]?.trim() || '0',
        })),
      }),
    onSuccess: (data) => {
      queryClient.setQueryData(['budget', associationId, exerciceId], data);
      queryClient.invalidateQueries({ queryKey: ['synthese', associationId] });
      setSaved(true);
    },
  });

  const lignes = useMemo(() => budget?.lignes ?? [], [budget]);
  const recettes = useMemo(() => lignes.filter((l) => l.sens === 'recette'), [lignes]);
  const depenses = useMemo(() => lignes.filter((l) => l.sens === 'depense'), [lignes]);

  const prevu = (l: LigneBudget) => Number(montants[l.categorie_id]?.trim() || 0);
  const totals = {
    recettesPrevu: sum(recettes, prevu),
    recettesRealise: sum(recettes, (l) => Number(l.realise)),
    depensesPrevu: sum(depenses, prevu),
    depensesRealise: sum(depenses, (l) => Number(l.realise)),
  };
  const resultatPrevu = totals.recettesPrevu - totals.depensesPrevu;
  const resultatRealise = totals.recettesRealise - totals.depensesRealise;

  const isCloture = budget?.exercice_statut === 'cloture';
  const readOnly = !canManage || isCloture;
  const dirty = lignes.some(
    (l) => cents(montants[l.categorie_id] ?? '') !== cents(l.montant_prevu)
  );

  function setMontant(categorieId: string, value: string) {
    setSaved(false);
    setMontants((m) => ({ ...m, [categorieId]: value }));
  }

  const selectedExercice = exerciceId || budget?.exercice_id || '';
  const saveError = apiErrorMessage(saveMutation, 'Enregistrement impossible.');

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold tracking-tight text-ink">Budget</h2>
          <p className="mt-1 text-sm text-muted">
            Le prévu par catégorie, comparé au réalisé de l’exercice.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Select
            aria-label="Exercice du budget"
            className="w-44"
            value={selectedExercice}
            onChange={(e) => {
              setExerciceId(e.target.value);
              setSaved(false);
            }}
          >
            {(exercicesQuery.data ?? []).map((ex) => (
              <option key={ex.id} value={ex.id}>
                {ex.libelle}
              </option>
            ))}
          </Select>
        </div>
      </div>

      {budgetQuery.isError ? (
        <Card className="p-5 text-sm text-muted">Impossible de charger le budget.</Card>
      ) : budgetQuery.isLoading || !budget ? (
        <Card className="space-y-3 p-5">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-8 animate-pulse rounded bg-hover" />
          ))}
        </Card>
      ) : (
        <>
          {isCloture && (
            <div className="flex items-center gap-2 text-sm text-muted">
              <Badge variant="neutral">Clôturé</Badge>
              <span>Exercice clôturé : le budget est en lecture seule.</span>
            </div>
          )}

          <Card className="overflow-hidden p-0">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[34rem] text-sm">
                <thead>
                  <tr className="border-b border-hairline text-xs uppercase tracking-wide text-faint">
                    <th className="px-4 py-2.5 text-left font-medium">Catégorie</th>
                    <th className="px-4 py-2.5 text-right font-medium">Prévu</th>
                    <th className="px-4 py-2.5 text-right font-medium">Réalisé</th>
                    <th className="px-4 py-2.5 text-right font-medium">Écart</th>
                  </tr>
                </thead>
                <BudgetSection
                  title="Recettes"
                  lignes={recettes}
                  montants={montants}
                  onChange={setMontant}
                  readOnly={readOnly}
                  totalPrevu={totals.recettesPrevu}
                  totalRealise={totals.recettesRealise}
                />
                <BudgetSection
                  title="Dépenses"
                  lignes={depenses}
                  montants={montants}
                  onChange={setMontant}
                  readOnly={readOnly}
                  totalPrevu={totals.depensesPrevu}
                  totalRealise={totals.depensesRealise}
                />
                <tfoot>
                  <tr className="border-t-2 border-hairline bg-hover font-semibold text-ink">
                    <td className="px-4 py-3">Résultat</td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      {formatEUR(resultatPrevu)}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      <span className={resultatRealise < 0 ? 'text-depense' : 'text-recette'}>
                        {formatEUR(resultatRealise)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <EcartCell sens="recette" ecart={resultatRealise - resultatPrevu} />
                    </td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </Card>

          <p className="text-xs text-faint">
            L’écart est le réalisé moins le prévu. Le réalisé ne compte que les écritures validées
            de l’exercice.
          </p>

          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() =>
                  triggerDownload(budgetApi.budgetPdfUrl(associationId, selectedExercice))
                }
              >
                <FileText className="h-4 w-4" aria-hidden />
                PDF
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() =>
                  triggerDownload(budgetApi.budgetXlsxUrl(associationId, selectedExercice))
                }
              >
                <FileSpreadsheet className="h-4 w-4" aria-hidden />
                Excel
              </Button>
            </div>
            {!readOnly && (
              <div className="flex items-center gap-3">
                {saveError && <span className="text-sm text-depense">{saveError}</span>}
                {saved && !dirty && (
                  <span className="inline-flex items-center gap-1 text-sm text-recette">
                    <Check className="h-4 w-4" aria-hidden />
                    Enregistré
                  </span>
                )}
                <Button
                  onClick={() => saveMutation.mutate()}
                  disabled={!dirty || saveMutation.isPending}
                >
                  {saveMutation.isPending ? 'Enregistrement…' : 'Enregistrer le budget'}
                </Button>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function BudgetSection({
  title,
  lignes,
  montants,
  onChange,
  readOnly,
  totalPrevu,
  totalRealise,
}: {
  title: string;
  lignes: LigneBudget[];
  montants: Montants;
  onChange: (categorieId: string, value: string) => void;
  readOnly: boolean;
  totalPrevu: number;
  totalRealise: number;
}) {
  if (lignes.length === 0) return null;
  return (
    <tbody className="divide-y divide-hairline">
      <tr className="bg-hover">
        <td
          colSpan={4}
          className="px-4 py-2 text-xs font-semibold uppercase tracking-wide text-ink-soft"
        >
          {title}
        </td>
      </tr>
      {lignes.map((l) => {
        const ecart = Number(l.realise) - Number(montants[l.categorie_id]?.trim() || 0);
        return (
          <tr key={l.categorie_id} className="hover:bg-hover">
            <td className="px-4 py-2 text-ink">{l.libelle}</td>
            <td className="px-4 py-2 text-right">
              <Input
                type="number"
                inputMode="decimal"
                min="0"
                step="0.01"
                disabled={readOnly}
                aria-label={`Budget prévu pour ${l.libelle}`}
                placeholder="0,00"
                className="ml-auto h-9 w-32 text-right tabular-nums"
                value={montants[l.categorie_id] ?? ''}
                onChange={(e) => onChange(l.categorie_id, e.target.value)}
              />
            </td>
            <td className="px-4 py-2 text-right tabular-nums text-ink-soft">
              {formatEUR(l.realise)}
            </td>
            <td className="px-4 py-2 text-right">
              <EcartCell sens={l.sens} ecart={ecart} />
            </td>
          </tr>
        );
      })}
      <tr className="bg-canvas font-medium text-ink-soft">
        <td className="px-4 py-2">Total {title.toLowerCase()}</td>
        <td className="px-4 py-2 text-right tabular-nums">{formatEUR(totalPrevu)}</td>
        <td className="px-4 py-2 text-right tabular-nums">{formatEUR(totalRealise)}</td>
        <td className="px-4 py-2" />
      </tr>
    </tbody>
  );
}
