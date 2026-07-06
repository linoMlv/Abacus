import { useQuery } from '@tanstack/react-query';
import { ArrowRight, Plus } from 'lucide-react';
import { lazy, Suspense, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import { accountingApi, type CompteTresorerie } from '@/api/accounting';
import { EvenementCard } from '@/components/evenements/EvenementCard';
import { AlertesPanel } from '@/components/synthese/AlertesPanel';
import { BudgetWidget } from '@/components/synthese/BudgetWidget';
import { ChartsSkeleton } from '@/components/synthese/ChartsSkeleton';
import { type Preset, presetParams } from '@/components/synthese/period';
import { PeriodControl } from '@/components/synthese/PeriodControl';
import { StatTile } from '@/components/synthese/StatTile';
import { TreasuryCard } from '@/components/synthese/TreasuryCard';
import { TreasuryAccountDialog } from '@/components/TreasuryAccountDialog';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { useActiveAssociation } from '@/hooks/useActiveAssociation';
import { usePermissions } from '@/hooks/usePermissions';
import { formatDate, formatEUR } from '@/lib/format';
import { PERMISSIONS } from '@/lib/permissions';

// Charts live in a lazily-loaded chunk so recharts never weighs on the main bundle.
const SyntheseCharts = lazy(() => import('@/components/charts/SyntheseCharts'));

export function SynthesePage() {
  const { associationId } = useParams() as { associationId: string };
  const navigate = useNavigate();
  const association = useActiveAssociation();
  const { has } = usePermissions();
  const canManage = has(PERMISSIONS.TRESORERIE_MANAGE);

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<CompteTresorerie | null>(null);
  const [preset, setPreset] = useState<Preset>('exercice');
  const [customFrom, setCustomFrom] = useState('');
  const [customTo, setCustomTo] = useState('');

  const params = useMemo(
    () => presetParams(preset, customFrom, customTo),
    [preset, customFrom, customTo]
  );

  const tresorerieQuery = useQuery({
    queryKey: ['tresorerie', associationId],
    queryFn: () => accountingApi.listTresorerie(associationId),
  });
  const comptes = tresorerieQuery.data ?? [];
  const total = comptes.reduce((sum, c) => sum + Number(c.solde), 0);

  const syntheseQuery = useQuery({
    queryKey: ['synthese', associationId, params],
    queryFn: () => accountingApi.getSynthese(associationId, params),
  });
  const synthese = syntheseQuery.data;

  const evenementsQuery = useQuery({
    queryKey: ['evenements', associationId],
    queryFn: () => accountingApi.listEvenements(associationId),
  });
  const evenements = evenementsQuery.data ?? [];
  const gererEvenements = () => navigate(`/asso/${associationId}/saisie?tab=evenements`);

  function openCreate() {
    setEditing(null);
    setDialogOpen(true);
  }

  function openEdit(compte: CompteTresorerie) {
    setEditing(compte);
    setDialogOpen(true);
  }

  function statValue(amount: string | undefined): string {
    if (syntheseQuery.isLoading) return '…';
    if (amount === undefined) return '—';
    return formatEUR(amount);
  }

  const resultatTone = synthese && Number(synthese.resultat.resultat) < 0 ? 'depense' : 'recette';
  const hasChartData =
    !!synthese &&
    (synthese.courbe_tresorerie.length > 0 ||
      synthese.repartition_categories.length > 0 ||
      synthese.repartition_evenements.length > 0);

  return (
    <div className="mx-auto max-w-6xl space-y-7">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold tracking-tight text-ink">
            {association?.name ?? 'Synthèse'}
          </h2>
          <p className="mt-1 text-sm text-muted">
            {synthese
              ? `Période du ${formatDate(synthese.date_from)} au ${formatDate(synthese.date_to)}`
              : 'Vue d’ensemble'}
          </p>
        </div>
        <PeriodControl
          preset={preset}
          onPreset={setPreset}
          customFrom={customFrom}
          customTo={customTo}
          onCustomFrom={setCustomFrom}
          onCustomTo={setCustomTo}
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile
          label="Trésorerie"
          value={tresorerieQuery.isLoading ? '…' : formatEUR(total)}
          hint="Solde consolidé des comptes"
        />
        <StatTile
          label="Résultat"
          value={statValue(synthese?.resultat.resultat)}
          hint="Produits − charges de la période"
          tone={synthese ? resultatTone : undefined}
        />
        <StatTile
          label="Recettes"
          value={statValue(synthese?.resultat.recettes)}
          hint="Produits de la période"
          tone="recette"
        />
        <StatTile
          label="Dépenses"
          value={statValue(synthese?.resultat.depenses)}
          hint="Charges de la période"
          tone="depense"
        />
      </div>

      {synthese && <AlertesPanel synthese={synthese} associationId={associationId} />}

      {synthese?.budget && <BudgetWidget budget={synthese.budget} associationId={associationId} />}

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-ink-soft">Comptes de trésorerie</h3>
          {canManage && (
            <Button variant="outline" size="sm" onClick={openCreate}>
              <Plus className="h-4 w-4" aria-hidden />
              Nouveau compte
            </Button>
          )}
        </div>
        {tresorerieQuery.isError ? (
          <Card className="p-5 text-sm text-muted">
            Impossible de charger les comptes de trésorerie.
          </Card>
        ) : comptes.length === 0 && !tresorerieQuery.isLoading ? (
          <Card className="p-5 text-sm text-muted">
            Aucun compte de trésorerie{canManage ? ' — créez-en un pour démarrer.' : '.'}
          </Card>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {comptes.map((compte) => (
              <TreasuryCard
                key={compte.id}
                compte={compte}
                onEdit={canManage ? () => openEdit(compte) : undefined}
              />
            ))}
          </div>
        )}
      </section>

      {evenements.length > 0 && (
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-ink-soft">Événements</h3>
            <Button variant="ghost" size="sm" onClick={gererEvenements}>
              Gérer
            </Button>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {evenements.map((evenement) => (
              <EvenementCard key={evenement.id} evenement={evenement} onOpen={gererEvenements} />
            ))}
          </div>
        </section>
      )}

      {syntheseQuery.isError ? (
        <Card className="p-5 text-sm text-muted">Impossible de charger la synthèse.</Card>
      ) : hasChartData ? (
        <Suspense fallback={<ChartsSkeleton />}>
          <SyntheseCharts synthese={synthese} />
        </Suspense>
      ) : synthese && !syntheseQuery.isLoading ? (
        <Card className="flex flex-col items-center gap-4 px-6 py-12 text-center">
          <div>
            <h3 className="text-base font-semibold text-ink">Aucun mouvement sur la période</h3>
            <p className="mx-auto mt-1.5 max-w-sm text-sm text-muted">
              Saisissez une recette ou une dépense : Abacus génère l’écriture comptable et met les
              soldes à jour.
            </p>
          </div>
          <Button onClick={() => navigate(`/asso/${associationId}/saisie`)}>
            Saisir une opération
            <ArrowRight className="h-4 w-4" aria-hidden />
          </Button>
        </Card>
      ) : null}

      {canManage && (
        <TreasuryAccountDialog
          associationId={associationId}
          compte={editing}
          open={dialogOpen}
          onOpenChange={setDialogOpen}
        />
      )}
    </div>
  );
}
