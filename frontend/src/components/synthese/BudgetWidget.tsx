import { PiggyBank } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

import type { BudgetSynthese } from '@/api/accounting';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { formatEUR } from '@/lib/format';
import { cn } from '@/lib/utils';

/** Compact budget pilotage card: dépenses consumption + prévisionnel result. */
export function BudgetWidget({
  budget,
  associationId,
}: {
  budget: BudgetSynthese;
  associationId: string;
}) {
  const navigate = useNavigate();
  const prevu = Number(budget.depenses_prevu);
  const realise = Number(budget.depenses_realise);
  const pct = prevu > 0 ? Math.min(100, (realise / prevu) * 100) : 0;
  const over = prevu > 0 && realise > prevu;
  const resultatRealise = Number(budget.resultat_realise);

  return (
    <Card className="space-y-4 p-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <PiggyBank className="h-4 w-4 text-faint" aria-hidden />
          <h3 className="text-sm font-semibold text-ink-soft">Budget {budget.exercice_libelle}</h3>
        </div>
        <Button variant="ghost" size="sm" onClick={() => navigate(`/asso/${associationId}/budget`)}>
          Ouvrir
        </Button>
      </div>

      <div className="space-y-1.5">
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted">Dépenses</span>
          <span className="tabular-nums text-ink">
            {formatEUR(budget.depenses_realise)}{' '}
            <span className="text-faint">/ {formatEUR(budget.depenses_prevu)}</span>
          </span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-hover">
          <div
            className={cn('h-full rounded-full', over ? 'bg-depense' : 'bg-accent')}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      <div className="flex items-center justify-between text-sm">
        <span className="text-muted">Résultat prévu / réalisé</span>
        <span className="tabular-nums">
          <span className="text-ink-soft">{formatEUR(budget.resultat_prevu)}</span>
          <span className="text-faint"> / </span>
          <span className={resultatRealise < 0 ? 'text-depense' : 'text-recette'}>
            {formatEUR(budget.resultat_realise)}
          </span>
        </span>
      </div>

      {budget.depassements.length > 0 && (
        <p className="text-xs text-depense">
          {budget.depassements.length} poste{budget.depassements.length > 1 ? 's' : ''} en
          dépassement : {budget.depassements.map((d) => d.libelle).join(', ')}
        </p>
      )}
    </Card>
  );
}
