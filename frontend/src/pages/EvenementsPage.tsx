import { useQuery } from '@tanstack/react-query';
import { ArrowLeft, CalendarRange, Download, Pencil, Plus } from 'lucide-react';
import { useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';

import {
  accountingApi,
  type EcritureListItem,
  type Evenement,
  EVENEMENT_STATUT_LABELS,
} from '@/api/accounting';
import { EvenementDialog } from '@/components/EvenementDialog';
import { Alert } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { useActiveAssociation } from '@/hooks/useActiveAssociation';
import { triggerDownload } from '@/lib/download';
import { formatDate, formatEUR } from '@/lib/format';
import { canManageEvenement } from '@/lib/roles';

const ACCENT = 'var(--color-accent)';

function accentOf(evenement: Evenement): string {
  return evenement.couleur ?? ACCENT;
}

function StatutBadge({ evenement }: { evenement: Evenement }) {
  return (
    <Badge variant={evenement.statut === 'actif' ? 'recette' : 'neutral'}>
      {EVENEMENT_STATUT_LABELS[evenement.statut]}
    </Badge>
  );
}

/** A budget line: réalisé vs budget, with a progress bar tinted by direction. */
function BudgetRow({
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

function ResultatLine({ evenement }: { evenement: Evenement }) {
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

function EvenementCard({
  evenement,
  onOpen,
  onEdit,
  bilanHref,
}: {
  evenement: Evenement;
  onOpen: () => void;
  onEdit?: () => void;
  bilanHref: string;
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
            <button
              type="button"
              onClick={() => triggerDownload(bilanHref)}
              aria-label={`Bilan PDF de ${evenement.nom}`}
              className="rounded-md p-1 text-faint transition-colors hover:bg-hover hover:text-ink"
            >
              <Download className="h-4 w-4" />
            </button>
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

/** Operations tagged to the open event (read-only). */
function EvenementOperations({
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

export function EvenementsPage() {
  const { associationId } = useParams() as { associationId: string };
  const association = useActiveAssociation();
  const canManage = association ? canManageEvenement(association.role) : false;

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Evenement | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);

  const query = useQuery({
    queryKey: ['evenements', associationId],
    queryFn: () => accountingApi.listEvenements(associationId),
  });
  const evenements = useMemo(() => query.data ?? [], [query.data]);
  const open = openId ? (evenements.find((e) => e.id === openId) ?? null) : null;

  function openCreate() {
    setEditing(null);
    setDialogOpen(true);
  }

  function openEdit(evenement: Evenement) {
    setEditing(evenement);
    setDialogOpen(true);
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      {open ? (
        <EvenementDetail
          associationId={associationId}
          evenement={open}
          canManage={canManage}
          onBack={() => setOpenId(null)}
          onEdit={() => openEdit(open)}
        />
      ) : (
        <>
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h2 className="text-xl font-semibold tracking-tight text-ink">Événements</h2>
              <p className="mt-1 text-sm text-muted">
                Suivez les recettes et dépenses de vos actions, budget à l’appui.
              </p>
            </div>
            {canManage && (
              <Button variant="accent" onClick={openCreate}>
                <Plus className="h-4 w-4" aria-hidden />
                Nouvel événement
              </Button>
            )}
          </div>

          {query.isError ? (
            <Alert>Impossible de charger les événements.</Alert>
          ) : evenements.length === 0 && !query.isLoading ? (
            <EmptyState canManage={canManage} onCreate={openCreate} />
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {evenements.map((evenement) => (
                <EvenementCard
                  key={evenement.id}
                  evenement={evenement}
                  onOpen={() => setOpenId(evenement.id)}
                  onEdit={canManage ? () => openEdit(evenement) : undefined}
                  bilanHref={accountingApi.evenementBilanPdfUrl(associationId, evenement.id)}
                />
              ))}
            </div>
          )}
        </>
      )}

      {canManage && (
        <EvenementDialog
          associationId={associationId}
          evenement={editing}
          open={dialogOpen}
          onOpenChange={setDialogOpen}
        />
      )}
    </div>
  );
}

function EmptyState({ canManage, onCreate }: { canManage: boolean; onCreate: () => void }) {
  return (
    <Card className="flex flex-col items-center gap-3 px-6 py-14 text-center">
      <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-accent-soft text-accent">
        <CalendarRange className="h-5 w-5" aria-hidden />
      </span>
      <h3 className="text-base font-semibold text-ink">Aucun événement pour l’instant</h3>
      <p className="max-w-sm text-sm text-muted">
        Créez un événement (Gala, sortie, tournoi…) puis rattachez-y vos opérations pour suivre son
        budget.
      </p>
      {canManage && (
        <Button variant="accent" onClick={onCreate}>
          <Plus className="h-4 w-4" aria-hidden />
          Nouvel événement
        </Button>
      )}
    </Card>
  );
}

function EvenementDetail({
  associationId,
  evenement,
  canManage,
  onBack,
  onEdit,
}: {
  associationId: string;
  evenement: Evenement;
  canManage: boolean;
  onBack: () => void;
  onEdit: () => void;
}) {
  return (
    <div className="space-y-6">
      <button
        type="button"
        onClick={onBack}
        className="inline-flex items-center gap-1.5 text-sm font-medium text-muted hover:text-ink"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden />
        Tous les événements
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
        {canManage && (
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
