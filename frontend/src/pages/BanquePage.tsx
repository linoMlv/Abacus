import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Building2, Upload } from 'lucide-react';
import { useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';

import {
  accountingApi,
  type CompteTresorerie,
  type LigneBancaire,
  type LigneBancaireStatut,
  LIGNE_BANCAIRE_STATUT_LABELS,
} from '@/api/accounting';
import { ImportReleveDialog } from '@/components/banque/ImportReleveDialog';
import { ReconcileDialog } from '@/components/banque/ReconcileDialog';
import { Alert } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Select } from '@/components/ui/select';
import { usePermissions } from '@/hooks/usePermissions';
import { formatDate, formatEUR } from '@/lib/format';
import { PERMISSIONS } from '@/lib/permissions';

type StatutFilter = 'tous' | LigneBancaireStatut;

const STATUT_BADGE: Record<LigneBancaireStatut, 'warning' | 'accent' | 'neutral'> = {
  non_rapproche: 'warning',
  rapproche: 'accent',
  ignore: 'neutral',
};

const FILTERS: { value: StatutFilter; label: string }[] = [
  { value: 'non_rapproche', label: 'À rapprocher' },
  { value: 'rapproche', label: 'Rapprochées' },
  { value: 'ignore', label: 'Ignorées' },
  { value: 'tous', label: 'Toutes' },
];

export function BanquePage() {
  const { associationId } = useParams() as { associationId: string };
  const { has } = usePermissions();
  const canReconcile = has(PERMISSIONS.BANK_RECONCILE);
  const [compteId, setCompteId] = useState('');
  const [filter, setFilter] = useState<StatutFilter>('non_rapproche');
  const [importOpen, setImportOpen] = useState(false);
  const [reconciling, setReconciling] = useState<LigneBancaire | null>(null);

  const comptesQuery = useQuery({
    queryKey: ['tresorerie', associationId],
    queryFn: () => accountingApi.listTresorerie(associationId),
  });
  const comptes = useMemo(
    () => (comptesQuery.data ?? []).filter((c) => c.is_active),
    [comptesQuery.data]
  );
  const selected = compteId || comptes[0]?.id || '';
  const selectedCompte = comptes.find((c) => c.id === selected);

  const lignesQuery = useQuery({
    queryKey: ['banque', associationId, 'lignes', selected, filter],
    queryFn: () =>
      accountingApi.listLignesBancaires(associationId, {
        compte_id: selected,
        statut: filter === 'tous' ? undefined : filter,
      }),
    enabled: !!selected,
  });
  const lignes = lignesQuery.data ?? [];

  if (comptesQuery.isSuccess && comptes.length === 0) {
    return (
      <Page>
        <Card className="p-8 text-center">
          <Building2 className="mx-auto h-8 w-8 text-faint" aria-hidden />
          <p className="mt-3 text-sm text-muted">
            Aucun compte de trésorerie. Créez-en un dans la Synthèse pour importer un relevé.
          </p>
        </Card>
      </Page>
    );
  }

  return (
    <Page>
      <Card className="flex flex-wrap items-end justify-between gap-3 p-4">
        <div className="min-w-[220px] flex-1">
          <label htmlFor="banque-compte" className="text-xs font-medium text-muted">
            Compte
          </label>
          <Select
            id="banque-compte"
            value={selected}
            onChange={(e) => setCompteId(e.target.value)}
            className="mt-1"
          >
            {comptes.map((c) => (
              <CompteOption key={c.id} compte={c} />
            ))}
          </Select>
        </div>
        {canReconcile && (
          <Button variant="accent" onClick={() => setImportOpen(true)} disabled={!selected}>
            <Upload className="h-4 w-4" aria-hidden />
            Importer un relevé
          </Button>
        )}
      </Card>

      <div className="flex flex-wrap gap-1.5">
        {FILTERS.map((f) => (
          <button
            key={f.value}
            type="button"
            onClick={() => setFilter(f.value)}
            className={`rounded-full px-3 py-1 text-sm transition-colors ${
              filter === f.value ? 'bg-ink text-white' : 'bg-hover text-muted hover:text-ink'
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {lignesQuery.isError ? (
        <Alert>Impossible de charger les opérations.</Alert>
      ) : lignesQuery.isLoading ? (
        <LignesSkeleton />
      ) : lignes.length === 0 ? (
        <Card className="p-8 text-center text-sm text-muted">
          {filter === 'non_rapproche'
            ? 'Aucune opération à rapprocher. Importez un relevé pour commencer.'
            : 'Aucune opération dans cette catégorie.'}
        </Card>
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] text-sm">
              <thead>
                <tr className="border-b border-hairline text-left text-xs text-faint">
                  <th className="px-4 py-2.5 font-medium">Date</th>
                  <th className="px-4 py-2.5 font-medium">Libellé</th>
                  <th className="px-4 py-2.5 text-right font-medium">Montant</th>
                  <th className="px-4 py-2.5 font-medium">Statut</th>
                  {canReconcile && <th className="px-4 py-2.5" />}
                </tr>
              </thead>
              <tbody className="divide-y divide-hairline">
                {lignes.map((ligne) => (
                  <LigneRow
                    key={ligne.id}
                    associationId={associationId}
                    ligne={ligne}
                    canReconcile={canReconcile}
                    onReconcile={() => setReconciling(ligne)}
                  />
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {importOpen && selectedCompte && (
        <ImportReleveDialog
          associationId={associationId}
          compteId={selectedCompte.id}
          compteLibelle={selectedCompte.libelle}
          open={importOpen}
          onClose={() => setImportOpen(false)}
          onImported={() => setFilter('non_rapproche')}
        />
      )}
      {reconciling && (
        <ReconcileDialog
          associationId={associationId}
          ligne={reconciling}
          open={!!reconciling}
          onClose={() => setReconciling(null)}
          onDone={() => setReconciling(null)}
        />
      )}
    </Page>
  );
}

function Page({ children }: { children: React.ReactNode }) {
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-xl font-semibold tracking-tight text-ink">Banque</h2>
        <p className="text-sm text-muted">
          Importez vos relevés et rapprochez chaque opération avec votre comptabilité.
        </p>
      </div>
      {children}
    </div>
  );
}

function CompteOption({ compte }: { compte: CompteTresorerie }) {
  return (
    <option value={compte.id}>
      {compte.libelle} · {formatEUR(compte.solde)}
    </option>
  );
}

function LigneRow({
  associationId,
  ligne,
  canReconcile,
  onReconcile,
}: {
  associationId: string;
  ligne: LigneBancaire;
  canReconcile: boolean;
  onReconcile: () => void;
}) {
  const queryClient = useQueryClient();
  const montant = Number(ligne.montant);
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['banque', associationId] });

  const ignorer = useMutation({
    mutationFn: (ignore: boolean) => accountingApi.ignorerLigne(associationId, ligne.id, ignore),
    onSuccess: invalidate,
  });
  const delettrer = useMutation({
    mutationFn: () => accountingApi.delettrerLigne(associationId, ligne.id),
    onSuccess: invalidate,
  });

  const busy = ignorer.isPending || delettrer.isPending;

  return (
    <tr className="hover:bg-hover/50">
      <td className="whitespace-nowrap px-4 py-2.5 text-muted">
        {formatDate(ligne.date_operation)}
      </td>
      <td className="max-w-[280px] truncate px-4 py-2.5 text-ink">{ligne.libelle}</td>
      <td
        className={`whitespace-nowrap px-4 py-2.5 text-right font-mono tabular-nums ${
          montant >= 0 ? 'text-recette' : 'text-depense'
        }`}
      >
        {formatEUR(ligne.montant)}
      </td>
      <td className="px-4 py-2.5">
        <Badge variant={STATUT_BADGE[ligne.statut]}>
          {LIGNE_BANCAIRE_STATUT_LABELS[ligne.statut]}
        </Badge>
      </td>
      {canReconcile && (
        <td className="px-4 py-2.5">
          <div className="flex justify-end gap-1.5">
            {ligne.statut === 'non_rapproche' && (
              <>
                <Button size="sm" variant="accent" onClick={onReconcile}>
                  Rapprocher
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  disabled={busy}
                  onClick={() => ignorer.mutate(true)}
                >
                  Ignorer
                </Button>
              </>
            )}
            {ligne.statut === 'rapproche' && (
              <Button
                size="sm"
                variant="outline"
                disabled={busy}
                onClick={() => delettrer.mutate()}
              >
                Délettrer
              </Button>
            )}
            {ligne.statut === 'ignore' && (
              <Button
                size="sm"
                variant="ghost"
                disabled={busy}
                onClick={() => ignorer.mutate(false)}
              >
                Réactiver
              </Button>
            )}
          </div>
        </td>
      )}
    </tr>
  );
}

function LignesSkeleton() {
  return (
    <Card className="divide-y divide-hairline">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="flex items-center gap-4 px-4 py-3">
          <div className="h-3 w-20 animate-pulse rounded bg-hairline" />
          <div className="h-3 flex-1 animate-pulse rounded bg-hairline" />
          <div className="h-3 w-16 animate-pulse rounded bg-hairline" />
        </div>
      ))}
    </Card>
  );
}
