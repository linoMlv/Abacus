import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Lock, Pencil, Plus, Search } from 'lucide-react';
import { useState } from 'react';
import { useParams } from 'react-router-dom';

import { accountingApi, CLASSES, type Compte } from '@/api/accounting';
import { apiErrorMessage } from '@/api/client';
import { CompteDialog } from '@/components/comptes/CompteDialog';
import { Alert } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { useDebounced } from '@/hooks/useDebounced';
import { usePermissions } from '@/hooks/usePermissions';
import { formatEUR } from '@/lib/format';
import { PERMISSIONS } from '@/lib/permissions';
import { cn } from '@/lib/utils';

/**
 * The chart of accounts, read as plain language first (C4): accounts are grouped
 * under their family ("Dépenses", "Recettes"…), the number stays secondary, and
 * the balance sits next to each account that actually carries movements — which
 * is also what "afficher seulement les comptes utilisés" filters on (§6).
 *
 * Editing is guided and gated by ACCOUNT_MANAGE; treasury accounts are shown but
 * point back to Trésorerie, their single management path.
 */
export function PlanComptableTab() {
  const { associationId } = useParams() as { associationId: string };
  const { has } = usePermissions();
  const canManage = has(PERMISSIONS.ACCOUNT_MANAGE);
  const canSeeFigures = has(PERMISSIONS.REPORT_VIEW);
  const queryClient = useQueryClient();

  const [search, setSearch] = useState('');
  const debouncedSearch = useDebounced(search, 250);
  const [usedOnly, setUsedOnly] = useState(false);
  const [showArchived, setShowArchived] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Compte | null>(null);
  const [createClasse, setCreateClasse] = useState(6);

  const comptesQuery = useQuery({
    queryKey: ['plan-comptable', associationId, { search: debouncedSearch, showArchived }],
    queryFn: () =>
      accountingApi.listPlanComptable(associationId, {
        search: debouncedSearch || undefined,
        includeInactive: showArchived,
      }),
  });
  const balanceQuery = useQuery({
    queryKey: ['balance', associationId],
    queryFn: () => accountingApi.getBalance(associationId),
    enabled: canSeeFigures,
  });

  const archive = useMutation({
    mutationFn: (compte: Compte) =>
      accountingApi.modifierCompte(associationId, compte.id, { is_active: !compte.is_active }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['plan-comptable', associationId] }),
  });

  const soldes = new Map((balanceQuery.data ?? []).map((b) => [b.compte_id, b.solde]));
  const comptes = (comptesQuery.data ?? []).filter((c) => !usedOnly || soldes.has(c.id));

  function openCreate(classe: number) {
    setEditing(null);
    setCreateClasse(classe);
    setDialogOpen(true);
  }

  function openEdit(compte: Compte) {
    setEditing(compte);
    setDialogOpen(true);
  }

  const archiveError = apiErrorMessage(archive, 'Action impossible.');

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative min-w-56 flex-1">
          <Search
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-faint"
            aria-hidden
          />
          <Input
            className="pl-9"
            placeholder="Rechercher un compte…"
            aria-label="Rechercher un compte"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        {canSeeFigures && (
          <Toggle checked={usedOnly} onChange={setUsedOnly} label="Comptes utilisés" />
        )}
        <Toggle checked={showArchived} onChange={setShowArchived} label="Comptes archivés" />
      </div>

      {archiveError && <Alert>{archiveError}</Alert>}
      {comptesQuery.isError && <Alert>Impossible de charger le plan comptable.</Alert>}

      {CLASSES.map(({ classe, label, hint }) => {
        const rows = comptes.filter((c) => c.classe === classe);
        if (rows.length === 0 && (debouncedSearch || usedOnly)) return null;
        return (
          <section key={classe} className="space-y-2">
            <div className="flex items-end justify-between gap-3">
              <div>
                <h3 className="text-sm font-semibold text-ink-soft">{label}</h3>
                <p className="text-xs text-muted">{hint}</p>
              </div>
              {canManage && (
                <Button variant="outline" size="sm" onClick={() => openCreate(classe)}>
                  <Plus className="h-4 w-4" aria-hidden />
                  Ajouter
                </Button>
              )}
            </div>
            <Card className="divide-y divide-hairline">
              {rows.length === 0 ? (
                <p className="px-4 py-4 text-sm text-muted">Aucun compte dans cette famille.</p>
              ) : (
                rows.map((compte) => (
                  <CompteRow
                    key={compte.id}
                    compte={compte}
                    solde={soldes.get(compte.id)}
                    canManage={canManage}
                    busy={archive.isPending}
                    onEdit={() => openEdit(compte)}
                    onArchive={() => archive.mutate(compte)}
                  />
                ))
              )}
            </Card>
          </section>
        );
      })}

      {canManage && (
        <CompteDialog
          associationId={associationId}
          compte={editing}
          classe={createClasse}
          rubriques={comptesQuery.data ?? []}
          open={dialogOpen}
          onOpenChange={setDialogOpen}
        />
      )}
    </div>
  );
}

function CompteRow({
  compte,
  solde,
  canManage,
  busy,
  onEdit,
  onArchive,
}: {
  compte: Compte;
  solde?: string;
  canManage: boolean;
  busy: boolean;
  onEdit: () => void;
  onArchive: () => void;
}) {
  // A treasury account lives in Trésorerie (type, IBAN, colour, opening balance):
  // showing it here without its edit affordances keeps a single source of rules.
  const isTreasury = compte.classe === 5;

  return (
    <div className={cn('flex items-center gap-3 px-4 py-2.5', !compte.is_active && 'opacity-60')}>
      <span className="w-16 shrink-0 font-mono text-xs tabular-nums text-faint">
        {compte.numero}
      </span>
      <span className="flex-1 truncate text-sm text-ink">{compte.libelle}</span>
      {!compte.is_active && <Badge variant="warning">Archivé</Badge>}
      {solde !== undefined && (
        <span className="shrink-0 font-mono text-sm tabular-nums text-ink-soft">
          {formatEUR(solde)}
        </span>
      )}
      {canManage &&
        (isTreasury ? (
          <span
            className="flex items-center gap-1 text-xs text-faint"
            title="Ce compte se gère depuis la Trésorerie"
          >
            <Lock className="h-3.5 w-3.5" aria-hidden />
            Trésorerie
          </span>
        ) : (
          <>
            <Button variant="ghost" size="sm" onClick={onArchive} disabled={busy}>
              {compte.is_active ? 'Archiver' : 'Réactiver'}
            </Button>
            <button
              type="button"
              aria-label={`Renommer ${compte.libelle}`}
              onClick={onEdit}
              disabled={busy}
              className="rounded-md p-1 text-faint transition-colors hover:bg-hover hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent disabled:pointer-events-none disabled:opacity-40"
            >
              <Pencil className="h-4 w-4" />
            </button>
          </>
        ))}
    </div>
  );
}

function Toggle({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (value: boolean) => void;
  label: string;
}) {
  return (
    <label className="flex cursor-pointer items-center gap-2 text-sm text-ink-soft">
      <input
        type="checkbox"
        className="h-4 w-4 rounded border-hairline accent-accent"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
      />
      {label}
    </label>
  );
}
