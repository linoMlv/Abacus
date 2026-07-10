import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';
import { useForm } from 'react-hook-form';

import {
  accountingApi,
  type CompteTresorerie,
  type CreateTresorerieInput,
  TYPE_TRESORERIE_LABELS,
  type TypeTresorerie,
} from '@/api/accounting';
import { apiErrorMessage } from '@/api/client';
import { Alert } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import { today } from '@/lib/format';
import { amountToDecimalString } from '@/pages/saisie.schema';
import { type TresorerieForm, tresorerieSchema } from '@/pages/tresorerie.schema';

const TYPES = Object.keys(TYPE_TRESORERIE_LABELS) as TypeTresorerie[];

function FieldError({ message }: { message?: string }) {
  if (!message) return null;
  return <p className="mt-1 text-xs text-depense">{message}</p>;
}

/**
 * Create or edit a treasury account. Opening balance (an à-nouveau entry) is set
 * at creation only; editing renames / retypes / re-identifies, and archiving
 * (never deleting) keeps the ledger history valid.
 */
export function TreasuryAccountDialog({
  associationId,
  compte,
  open,
  onOpenChange,
}: {
  associationId: string;
  compte?: CompteTresorerie | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const isEdit = !!compte;
  const queryClient = useQueryClient();

  const form = useForm<TresorerieForm>({
    resolver: zodResolver(tresorerieSchema),
    defaultValues: {
      nom: '',
      type_tresorerie: 'banque',
      iban: '',
      solde_initial: '',
      date_solde_initial: today(),
    },
  });
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = form;

  // Sync the form whenever the dialog opens or the edited account changes.
  useEffect(() => {
    if (!open) return;
    reset({
      nom: compte?.libelle ?? '',
      type_tresorerie: compte?.type_tresorerie ?? 'banque',
      iban: compte?.iban ?? '',
      solde_initial: '',
      date_solde_initial: today(),
    });
  }, [open, compte, reset]);

  function invalidate() {
    queryClient.invalidateQueries({ queryKey: ['tresorerie', associationId] });
    queryClient.invalidateQueries({ queryKey: ['ecritures', associationId] });
    queryClient.invalidateQueries({ queryKey: ['balance', associationId] });
  }

  const mutation = useMutation({
    mutationFn: async (values: TresorerieForm) => {
      const iban = values.iban.trim() || undefined;
      const hasSolde = values.solde_initial.trim() !== '';
      if (isEdit) {
        await accountingApi.modifierCompteTresorerie(associationId, compte.id, {
          nom: values.nom,
          type_tresorerie: values.type_tresorerie,
          iban,
        });
        // Opening balance is a separate, idempotent action; only touch it when set.
        if (hasSolde) {
          await accountingApi.definirSoldeInitial(associationId, compte.id, {
            montant: amountToDecimalString(values.solde_initial),
            date_solde_initial: values.date_solde_initial || today(),
          });
        }
        return;
      }
      const input: CreateTresorerieInput = {
        nom: values.nom,
        type_tresorerie: values.type_tresorerie,
        iban,
      };
      if (hasSolde) {
        input.solde_initial = amountToDecimalString(values.solde_initial);
        input.date_solde_initial = values.date_solde_initial || today();
      }
      await accountingApi.creerCompteTresorerie(associationId, input);
    },
    onSuccess: () => {
      invalidate();
      onOpenChange(false);
    },
  });

  const archive = useMutation({
    mutationFn: () =>
      accountingApi.modifierCompteTresorerie(associationId, compte!.id, { is_active: false }),
    onSuccess: () => {
      invalidate();
      onOpenChange(false);
    },
  });

  const onSubmit = handleSubmit((values) => mutation.mutate(values));
  const error =
    apiErrorMessage(mutation, 'Enregistrement impossible.') ??
    apiErrorMessage(archive, 'Archivage impossible.');

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogTitle>{isEdit ? 'Modifier le compte' : 'Nouveau compte de trésorerie'}</DialogTitle>
        <DialogDescription>
          {isEdit
            ? 'Renommez le compte ou changez son type.'
            : 'Où se trouve l’argent : banque, caisse, plateforme en ligne…'}
        </DialogDescription>

        <form onSubmit={onSubmit} className="mt-5 space-y-4" noValidate>
          <div>
            <Label htmlFor="treso-nom">Nom</Label>
            <Input
              id="treso-nom"
              className="mt-1.5"
              placeholder="Compte courant Crédit Agricole"
              {...register('nom')}
            />
            <FieldError message={errors.nom?.message} />
          </div>

          <div>
            <Label htmlFor="treso-type">Type</Label>
            <Select id="treso-type" className="mt-1.5" {...register('type_tresorerie')}>
              {TYPES.map((t) => (
                <option key={t} value={t}>
                  {TYPE_TRESORERIE_LABELS[t]}
                </option>
              ))}
            </Select>
          </div>

          <div>
            <Label htmlFor="treso-iban">IBAN / identifiant (optionnel)</Label>
            <Input id="treso-iban" className="mt-1.5" {...register('iban')} />
            <FieldError message={errors.iban?.message} />
          </div>

          <div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <Label htmlFor="treso-solde">Solde initial (€, optionnel)</Label>
                <Input
                  id="treso-solde"
                  inputMode="decimal"
                  placeholder="0,00"
                  className="mt-1.5 text-right font-mono tabular-nums"
                  {...register('solde_initial')}
                />
                <FieldError message={errors.solde_initial?.message} />
              </div>
              <div>
                <Label htmlFor="treso-date">Au</Label>
                <Input
                  id="treso-date"
                  type="date"
                  className="mt-1.5"
                  {...register('date_solde_initial')}
                />
              </div>
            </div>
            {isEdit && (
              <p className="mt-1.5 text-xs text-faint">
                Définit le solde de départ s’il ne l’est pas encore (validé d’emblée). Une fois
                défini, il s’ajuste par une contre-passation. Laissez vide pour ne pas y toucher.
              </p>
            )}
          </div>

          {error && <Alert>{error}</Alert>}

          <div className="flex items-center justify-between gap-3 pt-1">
            {isEdit ? (
              <Button
                type="button"
                variant="ghost"
                className="text-depense"
                disabled={archive.isPending}
                onClick={() => archive.mutate()}
              >
                Archiver
              </Button>
            ) : (
              <span />
            )}
            <Button type="submit" variant="accent" disabled={mutation.isPending}>
              {mutation.isPending ? 'Enregistrement…' : isEdit ? 'Enregistrer' : 'Créer le compte'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
