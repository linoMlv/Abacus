import type { SyntheseResultat } from '@/api/accounting';
import { Card } from '@/components/ui/card';
import { formatEUR } from '@/lib/format';
import { cn } from '@/lib/utils';

function Term({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: 'recette' | 'depense';
}) {
  return (
    <div className="flex-1 text-center sm:text-left">
      <p className="text-[11px] font-medium uppercase tracking-wide text-muted">{label}</p>
      <p
        className={cn(
          'mt-1 font-mono text-xl font-semibold tabular',
          tone === 'recette' ? 'text-recette' : 'text-depense'
        )}
      >
        {formatEUR(value)}
      </p>
    </div>
  );
}

/**
 * The period's result as a legible equation: Recettes − Dépenses = Résultat. The
 * three terms sit in one strip with the operators between them, so the arithmetic
 * a treasurer already does in their head reads straight off the screen.
 */
export function ResultStrip({ resultat }: { resultat: SyntheseResultat }) {
  const positif = Number(resultat.resultat) >= 0;
  return (
    <Card className="flex flex-col items-stretch gap-3 p-5 sm:flex-row sm:items-center sm:gap-5">
      <Term label="Recettes" value={resultat.recettes} tone="recette" />
      <span className="hidden text-lg text-faint sm:block" aria-hidden>
        −
      </span>
      <Term label="Dépenses" value={resultat.depenses} tone="depense" />
      <span className="hidden text-lg text-faint sm:block" aria-hidden>
        =
      </span>
      <div className="flex-1 text-center sm:text-left">
        <p className="text-[11px] font-medium uppercase tracking-wide text-muted">Résultat</p>
        <p
          className={cn(
            'mt-1 font-mono text-xl font-semibold tabular',
            positif ? 'text-recette' : 'text-depense'
          )}
        >
          {formatEUR(resultat.resultat)}
        </p>
      </div>
    </Card>
  );
}
