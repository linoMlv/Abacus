import { useQuery } from '@tanstack/react-query';
import { ArrowLeft, Pencil } from 'lucide-react';

import {
  accountingApi,
  type EcritureListItem,
  type Evenement,
  EVENEMENT_STATUT_LABELS,
} from '@/api/accounting';
import { Alert } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { formatDate, formatEUR } from '@/lib/format';

const ACCENT = 'var(--color-accent)';

function accentOf(evenement: Evenement): string {
  return evenement.couleur ?? ACCENT;
}

export function StatutBadge({ evenement }: { evenement: Evenement }) {
  return (
    <Badge variant={evenement.statut === 'actif' ? 'recette' : 'neutral'}>
      {EVENEMENT_STATUT_LABELS[evenement.statut]}
    </Badge>
  );
}

/** A budget line: réalisé vs budget, with a progress bar tinted by direction. */
export function BudgetRow({
  label,
  realise,
  budget,
  tone,
}: {
  label: string;
  realise: string;
  budget: string | null;
  tone: 'recette' | 'depense';
}) {
  const realiseNum = Number(realise);
  const budgetNum = budget ? Number(budget) : null;
  const ratio = budgetNum && budgetNum > 0 ? realiseNum / budgetNum : null;
  const over = ratio !== null && ratio > 1;
  const barColor = tone === 'recette' ? 'var(--color-recette)' : 'var(--color-depense)';
  return (
    <div>
      <div className="flex items-baseline justify-between text-sm">
        <span className="text-muted">{label}</span>
        <span className="tabular text-ink">
          {formatEUR(realise)}
          {budget && <span className="text-faint"> / {formatEUR(budget)}</span>}
        </span>
      </div>
      <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-hover">
        {ratio !== null && (
          <div
            className="h-full rounded-full"
            style={{
              width: `${Math.min(100, ratio * 100)}%`,
              backgroundColor: over ? 'var(--color-depense)' : barColor,
            }}
          />
        )}
      </div>
      {over && (
        <p className="mt-1 text-xs text-depense">
          Budget dépassé de {formatEUR(realiseNum - budgetNum!)}.
        </p>
      )}
    </div>
  );
}

export function ResultatLine({ evenement }: { evenement: Evenement }) {
  const value = Number(evenement.resultat);
  const tone = value > 0 ? 'text-recette' : value < 0 ? 'text-depense' : 'text-ink';
  return (
    <div className="flex items-baseline justify-between border-t border-hairline pt-3">
      <span className="text-sm font-medium text-ink-soft">Résultat</span>
      <span className={`tabular text-base font-semibold ${tone}`}>
        {formatEUR(evenement.resultat)}
      </span>
    </div>
  );
}

/** A budget-vs-réalisé card. ``onEdit`` is shown only where management is allowed. */
export function EvenementCard({
  evenement,
  onOpen,
  onEdit,
}: {
  evenement: Evenement;
  onOpen: () => void;
  onEdit?: () => void;
}) {
  return (
    <Card className="flex flex-col overflow-hidden">
      <span className="h-1 w-full" style={{ backgroundColor: accentOf(evenement) }} aria-hidden />
      <div className="flex flex-1 flex-col gap-4 p-5">
        <div className="flex items-start justify-between gap-3">
          <button
            type="button"
            onClick={onOpen}
            className="min-w-0 flex-1 text-left"
            aria-label={`Ouvrir ${evenement.nom}`}
          >
            <p className="truncate font-semibold text-ink hover:text-accent">{evenement.nom}</p>
            {(evenement.date_debut || evenement.date_fin) && (
              <p className="mt-0.5 text-xs text-muted">
                {[evenement.date_debut, evenement.date_fin]
                  .filter(Boolean)
                  .map((d) => formatDate(d as string))
                  .join(' → ')}
              </p>
            )}
          </button>
          <div className="flex shrink-0 items-center gap-1.5">
            <StatutBadge evenement={evenement} />
            {onEdit && (
              <button
                type="button"
                onClick={onEdit}
                aria-label={`Modifier ${evenement.nom}`}
                className="rounded-md p-1 text-faint transition-colors hover:bg-hover hover:text-ink"
              >
                <Pencil className="h-4 w-4" />
              </button>
            )}
          </div>
        </div>

        <div className="space-y-3">
          <BudgetRow
            label="Recettes"
            realise={evenement.realise_recettes}
            budget={evenement.budget_recettes}
            tone="recette"
          />
          <BudgetRow
            label="Dépenses"
            realise={evenement.realise_depenses}
            budget={evenement.budget_depenses}
            tone="depense"
          />
          <ResultatLine evenement={evenement} />
        </div>
      </div>
    </Card>
  );
}

/** Operations tagged to an event (read-only). */
export function EvenementOperations({
  associationId,
  evenementId,
}: {
  associationId: string;
  evenementId: string;
}) {
  const query = useQuery({
    queryKey: ['ecritures', associationId, { evenementIds: [evenementId] }],
    queryFn: () => accountingApi.listEcritures(associationId, { evenement_id: [evenementId] }),
  });
  const rows = query.data ?? [];

  if (query.isLoading) return <p className="text-sm text-muted">Chargement des opérations…</p>;
  if (query.isError) return <Alert>Impossible de charger les opérations.</Alert>;
  if (rows.length === 0)
    return <p className="text-sm text-muted">Aucune opération rattachée à cet événement.</p>;

  return (
    <Card className="overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[30rem] text-sm">
          <thead>
            <tr className="border-b border-hairline text-left text-xs uppercase tracking-wider text-faint">
              <th className="px-4 py-2.5 font-medium">Date</th>
              <th className="px-4 py-2.5 font-medium">Pièce</th>
              <th className="px-4 py-2.5 font-medium">Libellé</th>
              <th className="px-4 py-2.5 text-right font-medium">Montant</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((e: EcritureListItem) => (
              <tr key={e.id} className="border-b border-hairline last:border-0">
                <td className="whitespace-nowrap px-4 py-2.5 text-muted">{formatDate(e.date)}</td>
                <td className="px-4 py-2.5 font-mono text-xs tabular-nums text-muted">
                  {e.numero_piece}
                </td>
                <td className="px-4 py-2.5 text-ink">{e.libelle}</td>
                <td className="px-4 py-2.5 text-right font-mono tabular-nums text-ink">
                  {formatEUR(e.montant)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

/** Full event view: budget summary + tagged operations. Read-only unless ``onEdit``. */
export function EvenementDetail({
  associationId,
  evenement,
  onBack,
  onEdit,
}: {
  associationId: string;
  evenement: Evenement;
  onBack: () => void;
  onEdit?: () => void;
}) {
  return (
    <div className="space-y-6">
      <button
        type="button"
        onClick={onBack}
        className="inline-flex items-center gap-1.5 text-sm font-medium text-muted hover:text-ink"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden />
        Retour
      </button>

      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <span
            className="mt-1 h-8 w-1.5 shrink-0 rounded-full"
            style={{ backgroundColor: accentOf(evenement) }}
            aria-hidden
          />
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-semibold tracking-tight text-ink">{evenement.nom}</h2>
              <StatutBadge evenement={evenement} />
            </div>
            {evenement.description && (
              <p className="mt-1 max-w-prose text-sm text-muted">{evenement.description}</p>
            )}
          </div>
        </div>
        {onEdit && (
          <Button variant="outline" size="sm" onClick={onEdit}>
            <Pencil className="h-4 w-4" aria-hidden />
            Modifier
          </Button>
        )}
      </div>

      <Card className="space-y-4 p-5">
        <BudgetRow
          label="Recettes"
          realise={evenement.realise_recettes}
          budget={evenement.budget_recettes}
          tone="recette"
        />
        <BudgetRow
          label="Dépenses"
          realise={evenement.realise_depenses}
          budget={evenement.budget_depenses}
          tone="depense"
        />
        <ResultatLine evenement={evenement} />
      </Card>

      <section className="space-y-3">
        <h3 className="text-sm font-semibold text-ink-soft">Opérations</h3>
        <EvenementOperations associationId={associationId} evenementId={evenement.id} />
      </section>
    </div>
  );
}
