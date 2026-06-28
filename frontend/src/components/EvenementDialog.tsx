import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Check } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';

import {
  accountingApi,
  type CreateEvenementInput,
  type Evenement,
  type EvenementStatut,
  type UpdateEvenementInput,
} from '@/api/accounting';
import { apiErrorMessage } from '@/api/client';
import { Alert } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { cn } from '@/lib/utils';
import { amountToDecimalString } from '@/pages/saisie.schema';
import { type EvenementForm, evenementSchema } from '@/pages/evenement.schema';

/** A sober preset palette so events stay visually distinct without a raw picker. */
const COLORS = ['#2563EB', '#7C3AED', '#059669', '#D97706', '#DC2626', '#0891B2'];

function FieldError({ message }: { message?: string }) {
  return message ? <p className="mt-1 text-xs text-depense">{message}</p> : null;
}

function emptyToUndef(value?: string): string | undefined {
  const trimmed = value?.trim();
  return trimmed ? trimmed : undefined;
}

export function EvenementDialog({
  associationId,
  evenement,
  open,
  onOpenChange,
  onSaved,
}: {
  associationId: string;
  evenement: Evenement | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved?: (evenement: Evenement) => void;
}) {
  const queryClient = useQueryClient();
  const isEdit = evenement !== null;
  const [couleur, setCouleur] = useState<string | null>(null);
  const [statut, setStatut] = useState<EvenementStatut>('actif');

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<EvenementForm>({ resolver: zodResolver(evenementSchema) });

  useEffect(() => {
    if (!open) return;
    reset({
      nom: evenement?.nom ?? '',
      description: evenement?.description ?? '',
      date_debut: evenement?.date_debut ?? '',
      date_fin: evenement?.date_fin ?? '',
      budget_recettes: evenement?.budget_recettes ?? '',
      budget_depenses: evenement?.budget_depenses ?? '',
    });
    setCouleur(evenement?.couleur ?? null);
    setStatut(evenement?.statut ?? 'actif');
  }, [open, evenement, reset]);

  const mutation = useMutation({
    mutationFn: (values: EvenementForm) => {
      const payload: CreateEvenementInput = {
        nom: values.nom.trim(),
        description: emptyToUndef(values.description),
        date_debut: emptyToUndef(values.date_debut),
        date_fin: emptyToUndef(values.date_fin),
        budget_recettes: values.budget_recettes?.trim()
          ? amountToDecimalString(values.budget_recettes)
          : undefined,
        budget_depenses: values.budget_depenses?.trim()
          ? amountToDecimalString(values.budget_depenses)
          : undefined,
        couleur: couleur ?? undefined,
      };
      if (isEdit) {
        const update: UpdateEvenementInput = { ...payload, statut };
        return accountingApi.modifierEvenement(associationId, evenement.id, update);
      }
      return accountingApi.creerEvenement(associationId, payload);
    },
    onSuccess: (saved) => {
      queryClient.invalidateQueries({ queryKey: ['evenements', associationId] });
      queryClient.invalidateQueries({ queryKey: ['evenement', associationId, saved.id] });
      onSaved?.(saved);
      onOpenChange(false);
    },
  });

  const error = apiErrorMessage(mutation, 'Enregistrement impossible.');

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogTitle>{isEdit ? 'Modifier l’événement' : 'Nouvel événement'}</DialogTitle>
        <DialogDescription>
          Un événement regroupe les recettes et dépenses d’une action (Gala, sortie…) pour en suivre
          le budget.
        </DialogDescription>

        <form
          onSubmit={handleSubmit((values) => mutation.mutate(values))}
          className="mt-5 space-y-4"
          noValidate
        >
          <div>
            <Label htmlFor="ev-nom">Nom</Label>
            <Input id="ev-nom" className="mt-1.5" placeholder="Gala 2026" {...register('nom')} />
            <FieldError message={errors.nom?.message} />
          </div>

          <div>
            <Label htmlFor="ev-description">Description (optionnel)</Label>
            <textarea
              id="ev-description"
              rows={2}
              className={cn(
                'mt-1.5 w-full rounded-lg border border-hairline bg-surface px-3 py-2 text-sm text-ink',
                'placeholder:text-faint transition-colors',
                'focus-visible:border-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/30'
              )}
              placeholder="Objet de l’événement…"
              {...register('description')}
            />
            <FieldError message={errors.description?.message} />
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <Label htmlFor="ev-debut">Début (optionnel)</Label>
              <Input id="ev-debut" type="date" className="mt-1.5" {...register('date_debut')} />
            </div>
            <div>
              <Label htmlFor="ev-fin">Fin (optionnel)</Label>
              <Input id="ev-fin" type="date" className="mt-1.5" {...register('date_fin')} />
              <FieldError message={errors.date_fin?.message} />
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <Label htmlFor="ev-budget-r">Budget recettes (€)</Label>
              <Input
                id="ev-budget-r"
                inputMode="decimal"
                placeholder="0,00"
                className="mt-1.5 text-right font-mono tabular-nums"
                {...register('budget_recettes')}
              />
              <FieldError message={errors.budget_recettes?.message} />
            </div>
            <div>
              <Label htmlFor="ev-budget-d">Budget dépenses (€)</Label>
              <Input
                id="ev-budget-d"
                inputMode="decimal"
                placeholder="0,00"
                className="mt-1.5 text-right font-mono tabular-nums"
                {...register('budget_depenses')}
              />
              <FieldError message={errors.budget_depenses?.message} />
            </div>
          </div>

          <div>
            <span className="text-sm font-medium text-ink-soft">Couleur</span>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              {COLORS.map((c) => (
                <button
                  key={c}
                  type="button"
                  onClick={() => setCouleur(couleur === c ? null : c)}
                  aria-label={`Couleur ${c}`}
                  aria-pressed={couleur === c}
                  className="flex h-7 w-7 items-center justify-center rounded-full ring-offset-2 ring-offset-surface transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
                  style={{ backgroundColor: c }}
                >
                  {couleur === c && <Check className="h-4 w-4 text-white" aria-hidden />}
                </button>
              ))}
            </div>
          </div>

          {isEdit && (
            <label className="flex items-center gap-2.5 text-sm text-ink">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-hairline accent-accent"
                checked={statut === 'cloture'}
                onChange={(e) => setStatut(e.target.checked ? 'cloture' : 'actif')}
              />
              Événement clôturé
            </label>
          )}

          {error && <Alert>{error}</Alert>}

          <div className="flex justify-end gap-2 pt-1">
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
              Annuler
            </Button>
            <Button type="submit" variant="accent" disabled={mutation.isPending}>
              {mutation.isPending ? 'Enregistrement…' : isEdit ? 'Enregistrer' : 'Créer'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
