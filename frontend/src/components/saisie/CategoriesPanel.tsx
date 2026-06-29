import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ChevronDown, ChevronUp, Pencil, Plus } from 'lucide-react';
import { type ReactNode, useState } from 'react';
import { useParams } from 'react-router-dom';

import { accountingApi, type Categorie, type Sens } from '@/api/accounting';
import { CategorieDialog } from '@/components/CategorieDialog';
import { Alert } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { usePermissions } from '@/hooks/usePermissions';
import { PERMISSIONS } from '@/lib/permissions';
import { cn } from '@/lib/utils';

const SENS_SECTIONS: Array<{ sens: Sens; title: string }> = [
  { sens: 'recette', title: 'Recettes' },
  { sens: 'depense', title: 'Dépenses' },
];

/** Manage the saisie categories (create / rename / reorder / archive). */
export function CategoriesPanel() {
  const { associationId } = useParams() as { associationId: string };
  const { has } = usePermissions();
  const canManage = has(PERMISSIONS.CATEGORIE_MANAGE);
  const queryClient = useQueryClient();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Categorie | null>(null);
  const [defaultSens, setDefaultSens] = useState<Sens>('recette');

  const query = useQuery({
    queryKey: ['categories', associationId, { includeInactive: true }],
    queryFn: () => accountingApi.listCategories(associationId, undefined, true),
  });
  const categories = query.data ?? [];

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ['categories', associationId] });

  const toggleActive = useMutation({
    mutationFn: (cat: Categorie) =>
      accountingApi.modifierCategorie(associationId, cat.id, { is_active: !cat.is_active }),
    onSuccess: invalidate,
  });

  const reorder = useMutation({
    mutationFn: async ({ a, b }: { a: Categorie; b: Categorie }) => {
      await accountingApi.modifierCategorie(associationId, a.id, { ordre: b.ordre });
      await accountingApi.modifierCategorie(associationId, b.id, { ordre: a.ordre });
    },
    onSuccess: invalidate,
  });

  function openCreate(sens: Sens) {
    setEditing(null);
    setDefaultSens(sens);
    setDialogOpen(true);
  }

  function openEdit(cat: Categorie) {
    setEditing(cat);
    setDialogOpen(true);
  }

  const error = toggleActive.isError || reorder.isError ? 'Action impossible. Réessayez.' : null;

  return (
    <div className="space-y-6">
      <p className="text-sm text-muted">
        Les natures d’opération de la saisie. Désactiver une catégorie la retire de la saisie sans
        toucher aux écritures passées.
      </p>

      {error && <Alert>{error}</Alert>}
      {query.isError && <Alert>Impossible de charger les catégories.</Alert>}

      {SENS_SECTIONS.map(({ sens, title }) => {
        const rows = categories.filter((c) => c.sens === sens).sort((a, b) => a.ordre - b.ordre);
        return (
          <section key={sens} className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-ink-soft">{title}</h3>
              {canManage && (
                <Button variant="outline" size="sm" onClick={() => openCreate(sens)}>
                  <Plus className="h-4 w-4" aria-hidden />
                  Nouvelle
                </Button>
              )}
            </div>
            <Card className="divide-y divide-hairline">
              {rows.length === 0 ? (
                <p className="px-4 py-5 text-sm text-muted">Aucune catégorie.</p>
              ) : (
                rows.map((cat, index) => (
                  <CategorieRow
                    key={cat.id}
                    cat={cat}
                    canManage={canManage}
                    isFirst={index === 0}
                    isLast={index === rows.length - 1}
                    onEdit={() => openEdit(cat)}
                    onToggle={() => toggleActive.mutate(cat)}
                    onMoveUp={() => reorder.mutate({ a: cat, b: rows[index - 1] })}
                    onMoveDown={() => reorder.mutate({ a: cat, b: rows[index + 1] })}
                    busy={reorder.isPending || toggleActive.isPending}
                  />
                ))
              )}
            </Card>
          </section>
        );
      })}

      {canManage && (
        <CategorieDialog
          associationId={associationId}
          categorie={editing}
          defaultSens={defaultSens}
          open={dialogOpen}
          onOpenChange={setDialogOpen}
        />
      )}
    </div>
  );
}

function CategorieRow({
  cat,
  canManage,
  isFirst,
  isLast,
  onEdit,
  onToggle,
  onMoveUp,
  onMoveDown,
  busy,
}: {
  cat: Categorie;
  canManage: boolean;
  isFirst: boolean;
  isLast: boolean;
  onEdit: () => void;
  onToggle: () => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
  busy: boolean;
}) {
  return (
    <div className={cn('flex items-center gap-3 px-4 py-3', !cat.is_active && 'opacity-60')}>
      {canManage && (
        <div className="flex flex-col">
          <IconButton label="Monter" disabled={isFirst || busy} onClick={onMoveUp}>
            <ChevronUp className="h-3.5 w-3.5" />
          </IconButton>
          <IconButton label="Descendre" disabled={isLast || busy} onClick={onMoveDown}>
            <ChevronDown className="h-3.5 w-3.5" />
          </IconButton>
        </div>
      )}
      <span className="flex-1 truncate text-sm text-ink">{cat.libelle}</span>
      {!cat.is_active && <Badge variant="warning">Archivée</Badge>}
      {canManage && (
        <>
          <Button variant="ghost" size="sm" onClick={onToggle} disabled={busy}>
            {cat.is_active ? 'Archiver' : 'Réactiver'}
          </Button>
          <IconButton label={`Modifier ${cat.libelle}`} onClick={onEdit} disabled={busy}>
            <Pencil className="h-4 w-4" />
          </IconButton>
        </>
      )}
    </div>
  );
}

function IconButton({
  label,
  onClick,
  disabled,
  children,
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      onClick={onClick}
      disabled={disabled}
      className="rounded-md p-1 text-faint transition-colors hover:bg-hover hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent disabled:pointer-events-none disabled:opacity-40"
    >
      {children}
    </button>
  );
}
