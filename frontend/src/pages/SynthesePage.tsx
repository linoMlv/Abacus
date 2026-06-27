import { useQuery } from '@tanstack/react-query';
import { ArrowRight, Pencil, Plus, Wallet } from 'lucide-react';
import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import { accountingApi, type CompteTresorerie, TYPE_TRESORERIE_LABELS } from '@/api/accounting';
import { TreasuryAccountDialog } from '@/components/TreasuryAccountDialog';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { useActiveAssociation } from '@/hooks/useActiveAssociation';
import { formatEUR } from '@/lib/format';
import { canManageTresorerie } from '@/lib/roles';

function StatTile({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: string;
  hint: string;
  tone?: 'recette' | 'depense';
}) {
  const valueColor =
    tone === 'recette' ? 'text-recette' : tone === 'depense' ? 'text-depense' : 'text-ink';
  return (
    <Card className="p-5">
      <p className="text-xs font-medium uppercase tracking-wider text-faint">{label}</p>
      <p className={`tabular mt-3 text-2xl font-semibold ${valueColor}`}>{value}</p>
      <p className="mt-1 text-xs text-muted">{hint}</p>
    </Card>
  );
}

function TreasuryCard({ compte, onEdit }: { compte: CompteTresorerie; onEdit?: () => void }) {
  return (
    <Card className="flex items-center gap-4 p-4">
      <span
        className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg"
        style={{
          backgroundColor: compte.couleur ? `${compte.couleur}1a` : 'var(--color-accent-soft)',
          color: compte.couleur ?? 'var(--color-accent)',
        }}
        aria-hidden
      >
        <Wallet className="h-5 w-5" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-ink">{compte.libelle}</p>
        <p className="text-xs text-muted">{TYPE_TRESORERIE_LABELS[compte.type_tresorerie]}</p>
      </div>
      <p className="tabular shrink-0 text-base font-semibold text-ink">{formatEUR(compte.solde)}</p>
      {onEdit && (
        <button
          type="button"
          onClick={onEdit}
          aria-label={`Modifier ${compte.libelle}`}
          className="shrink-0 rounded-md p-1.5 text-faint transition-colors hover:bg-hover hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
        >
          <Pencil className="h-4 w-4" />
        </button>
      )}
    </Card>
  );
}

function sumSoldes(comptes: CompteTresorerie[]): number {
  return comptes.reduce((total, c) => total + Number(c.solde), 0);
}

export function SynthesePage() {
  const { associationId } = useParams() as { associationId: string };
  const navigate = useNavigate();
  const association = useActiveAssociation();
  const canManage = association ? canManageTresorerie(association.role) : false;

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<CompteTresorerie | null>(null);

  const tresorerieQuery = useQuery({
    queryKey: ['tresorerie', associationId],
    queryFn: () => accountingApi.listTresorerie(associationId),
  });
  const comptes = tresorerieQuery.data ?? [];
  const total = sumSoldes(comptes);

  function openCreate() {
    setEditing(null);
    setDialogOpen(true);
  }

  function openEdit(compte: CompteTresorerie) {
    setEditing(compte);
    setDialogOpen(true);
  }

  return (
    <div className="mx-auto max-w-6xl space-y-7">
      <div>
        <h2 className="text-xl font-semibold tracking-tight text-ink">
          {association?.name ?? 'Synthèse'}
        </h2>
        <p className="mt-1 text-sm text-muted">Vue d’ensemble de l’exercice en cours.</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile
          label="Trésorerie"
          value={tresorerieQuery.isLoading ? '…' : formatEUR(total)}
          hint="Solde consolidé des comptes"
        />
        <StatTile label="Résultat" value="—" hint="Exercice en cours" />
        <StatTile label="Recettes" value="—" hint="Cumul de l’exercice" tone="recette" />
        <StatTile label="Dépenses" value="—" hint="Cumul de l’exercice" tone="depense" />
      </div>

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

      <Card className="flex flex-col items-center gap-4 px-6 py-12 text-center">
        <div>
          <h3 className="text-base font-semibold text-ink">Enregistrer une opération</h3>
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
