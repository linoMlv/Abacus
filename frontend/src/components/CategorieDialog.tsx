import { useMutation, useQueryClient } from '@tanstack/react-query';
import { type FormEvent, useEffect, useState } from 'react';

import { accountingApi, type Categorie, type Sens } from '@/api/accounting';
import { apiErrorMessage } from '@/api/client';
import { Alert } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { cn } from '@/lib/utils';

/**
 * Create or rename an entry category. Soft creation needs only a name + sens; the
 * server auto-assigns the produit/charge account (the expert can reassign it from
 * the management screen). The sens is fixed once created (it drives the account).
 */
export function CategorieDialog({
  associationId,
  categorie,
  defaultSens = 'recette',
  open,
  onOpenChange,
  onSaved,
}: {
  associationId: string;
  categorie?: Categorie | null;
  defaultSens?: Sens;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved?: (categorie: Categorie) => void;
}) {
  const isEdit = !!categorie;
  const queryClient = useQueryClient();
  const [sens, setSens] = useState<Sens>(defaultSens);
  const [libelle, setLibelle] = useState('');

  useEffect(() => {
    if (!open) return;
    setSens(categorie?.sens ?? defaultSens);
    setLibelle(categorie?.libelle ?? '');
  }, [open, categorie, defaultSens]);

  const mutation = useMutation({
    mutationFn: () => {
      const nom = libelle.trim();
      if (isEdit) {
        return accountingApi.modifierCategorie(associationId, categorie.id, { libelle: nom });
      }
      return accountingApi.creerCategorie(associationId, { sens, libelle: nom });
    },
    onSuccess: (saved) => {
      queryClient.invalidateQueries({ queryKey: ['categories', associationId] });
      onSaved?.(saved);
      onOpenChange(false);
    },
  });

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!libelle.trim()) return;
    mutation.mutate();
  };

  const error = apiErrorMessage(mutation, 'Enregistrement impossible.');

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogTitle>{isEdit ? 'Modifier la catégorie' : 'Nouvelle catégorie'}</DialogTitle>
        <DialogDescription>
          {isEdit
            ? 'Renommez la catégorie.'
            : 'Le compte comptable est attribué automatiquement (ajustable ensuite).'}
        </DialogDescription>

        <form onSubmit={onSubmit} className="mt-5 space-y-4" noValidate>
          {!isEdit && (
            <div className="grid grid-cols-2 gap-2" role="group" aria-label="Sens">
              {(['recette', 'depense'] as const).map((s) => (
                <button
                  key={s}
                  type="button"
                  aria-pressed={sens === s}
                  onClick={() => setSens(s)}
                  className={cn(
                    'rounded-lg border px-4 py-2.5 text-sm font-medium transition-colors',
                    sens === s
                      ? s === 'recette'
                        ? 'border-recette bg-recette-soft text-recette'
                        : 'border-depense bg-depense-soft text-depense'
                      : 'border-hairline bg-surface text-ink-soft hover:bg-hover'
                  )}
                >
                  {s === 'recette' ? 'Recette' : 'Dépense'}
                </button>
              ))}
            </div>
          )}

          <div>
            <Label htmlFor="cat-libelle">Libellé</Label>
            <Input
              id="cat-libelle"
              className="mt-1.5"
              placeholder="Buvette, Loyer, Subvention…"
              value={libelle}
              onChange={(e) => setLibelle(e.target.value)}
              autoFocus
            />
          </div>

          {error && <Alert>{error}</Alert>}

          <div className="flex justify-end pt-1">
            <Button type="submit" variant="accent" disabled={mutation.isPending}>
              {mutation.isPending ? 'Enregistrement…' : isEdit ? 'Enregistrer' : 'Créer'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
