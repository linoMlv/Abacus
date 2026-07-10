import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ChevronDown, Plus, Trash2 } from 'lucide-react';
import { useMemo, useState } from 'react';
import { useFieldArray, useForm } from 'react-hook-form';
import { useParams } from 'react-router-dom';

import {
  accountingApi,
  type Ecriture,
  type EcritureContenu,
  MODE_REGLEMENT_LABELS,
  type SaisieManuelleInput,
} from '@/api/accounting';
import { apiErrorMessage } from '@/api/client';
import { Alert } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import { cents, formatEUR } from '@/lib/format';
import { invalidateAfterEntry } from '@/lib/queries';
import { cn } from '@/lib/utils';
import { MODE_REGLEMENT_VALUES } from '@/pages/saisie.schema';

import { fromEntry, type ManuelleForm, manuelleSchema, num, toDecimal } from './manualEntry.schema';

export interface ManualEntryFormProps {
  /** ``edit`` rebuilds a draft in place; ``correct`` annule-et-remplace a validated entry. */
  action: 'edit' | 'correct';
  entry: Ecriture;
  onSaved: () => void;
  onCancel: () => void;
}

/**
 * Multi-line editor for a manual (expert) entry, shared by draft edition (PATCH)
 * and the correction of a validated one (contre-passation with replacement). The
 * type-first operation form covers recette/dépense/virement; this one covers the
 * free, balanced multi-line origine those cannot express. The original is never
 * mutated in correct mode — its reversal and the corrected draft are booked.
 */
export function ManualEntryForm({ action, entry, onSaved, onCancel }: ManualEntryFormProps) {
  const isCorrect = action === 'correct';
  const { associationId } = useParams() as { associationId: string };
  const queryClient = useQueryClient();
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  const journauxQuery = useQuery({
    queryKey: ['journaux', associationId],
    queryFn: () => accountingApi.listJournaux(associationId),
  });
  const comptesQuery = useQuery({
    queryKey: ['comptes', associationId],
    queryFn: () => accountingApi.listComptes(associationId),
  });

  const journaux = useMemo(() => journauxQuery.data ?? [], [journauxQuery.data]);
  const comptes = useMemo(() => comptesQuery.data ?? [], [comptesQuery.data]);

  const {
    register,
    control,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<ManuelleForm>({
    resolver: zodResolver(manuelleSchema),
    defaultValues: fromEntry(entry),
  });
  const { fields, append, remove } = useFieldArray({ control, name: 'lignes' });

  const lignes = watch('lignes');
  const totalDebit = lignes.reduce((s, l) => s + num(l.debit), 0);
  const totalCredit = lignes.reduce((s, l) => s + num(l.credit), 0);
  const balanced = cents(totalDebit) === cents(totalCredit) && cents(totalDebit) > 0;

  const editMutation = useMutation({
    mutationFn: (contenu: EcritureContenu) =>
      accountingApi.modifierEcriture(associationId, entry.id, contenu),
  });
  const correctMutation = useMutation({
    mutationFn: (contenu: EcritureContenu) =>
      accountingApi.contrepasserEcriture(associationId, entry.id, { remplacement: contenu }),
  });
  const mutation = isCorrect ? correctMutation : editMutation;

  const onSubmit = handleSubmit(async (values) => {
    const manuelle: SaisieManuelleInput = {
      journal_id: values.journal_id,
      date: values.date,
      libelle: values.libelle.trim(),
      reference_externe: values.reference_externe?.trim() || undefined,
      mode_reglement: values.mode_reglement || undefined,
      lignes: values.lignes.map((l) => ({
        compte_id: l.compte_id,
        debit: toDecimal(l.debit),
        credit: toDecimal(l.credit),
      })),
    };
    setBusy(true);
    try {
      await mutation.mutateAsync({ manuelle });
      invalidateAfterEntry(queryClient, associationId);
      onSaved();
    } catch {
      // The mutation's error state drives the Alert below.
    } finally {
      setBusy(false);
    }
  });

  const error = apiErrorMessage(
    mutation,
    isCorrect ? 'Correction impossible.' : 'Modification impossible.'
  );
  const lignesError =
    (errors.lignes as { root?: { message?: string }; message?: string } | undefined)?.root
      ?.message ?? (errors.lignes as { message?: string } | undefined)?.message;

  return (
    <form onSubmit={onSubmit} className="space-y-5" noValidate>
      <div className="grid gap-5 sm:grid-cols-2">
        <div>
          <Label htmlFor="me-journal">Journal</Label>
          <Select id="me-journal" className="mt-1.5" {...register('journal_id')}>
            {journaux.length === 0 && <option value="">—</option>}
            {journaux.map((j) => (
              <option key={j.id} value={j.id}>
                {j.code} — {j.libelle}
              </option>
            ))}
          </Select>
          {errors.journal_id && (
            <p className="mt-1 text-xs text-depense">{errors.journal_id.message}</p>
          )}
        </div>
        <div>
          <Label htmlFor="me-date">Date</Label>
          <Input id="me-date" type="date" className="mt-1.5" {...register('date')} />
          {errors.date && <p className="mt-1 text-xs text-depense">{errors.date.message}</p>}
        </div>
      </div>

      <div>
        <Label htmlFor="me-libelle">Libellé</Label>
        <Input id="me-libelle" className="mt-1.5" {...register('libelle')} />
        {errors.libelle && <p className="mt-1 text-xs text-depense">{errors.libelle.message}</p>}
      </div>

      {/* Lines: each is a debit or a credit on an account. */}
      <div className="space-y-2">
        <div className="grid grid-cols-[1fr_5rem_5rem_2rem] items-center gap-2 text-xs font-medium uppercase tracking-wider text-faint">
          <span>Compte</span>
          <span className="text-right">Débit</span>
          <span className="text-right">Crédit</span>
          <span className="sr-only">Retirer</span>
        </div>
        {fields.map((field, i) => (
          <div key={field.id} className="grid grid-cols-[1fr_5rem_5rem_2rem] items-start gap-2">
            <div>
              <Select aria-label={`Compte ligne ${i + 1}`} {...register(`lignes.${i}.compte_id`)}>
                <option value="">—</option>
                {comptes.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.numero} — {c.libelle}
                  </option>
                ))}
              </Select>
              {errors.lignes?.[i]?.compte_id && (
                <p className="mt-1 text-xs text-depense">{errors.lignes[i]?.compte_id?.message}</p>
              )}
            </div>
            <Input
              aria-label={`Débit ligne ${i + 1}`}
              inputMode="decimal"
              placeholder="0,00"
              className="text-right font-mono tabular-nums"
              {...register(`lignes.${i}.debit`)}
            />
            <Input
              aria-label={`Crédit ligne ${i + 1}`}
              inputMode="decimal"
              placeholder="0,00"
              className="text-right font-mono tabular-nums"
              {...register(`lignes.${i}.credit`)}
            />
            <button
              type="button"
              onClick={() => remove(i)}
              disabled={fields.length <= 2}
              className="mt-2 rounded-md p-1 text-faint hover:bg-hover hover:text-depense disabled:cursor-not-allowed disabled:opacity-40"
              aria-label={`Retirer la ligne ${i + 1}`}
            >
              <Trash2 className="h-4 w-4" aria-hidden />
            </button>
          </div>
        ))}

        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() => append({ compte_id: '', debit: '', credit: '' })}
        >
          <Plus className="h-4 w-4" aria-hidden />
          Ajouter une ligne
        </Button>

        {/* Live balance: Σdebit must equal Σcredit. */}
        <div
          className={cn(
            'grid grid-cols-[1fr_5rem_5rem_2rem] items-center gap-2 rounded-lg border px-2 py-2 text-sm',
            balanced ? 'border-recette/20 bg-recette-soft' : 'border-depense/20 bg-depense-soft'
          )}
        >
          <span className={cn('font-medium', balanced ? 'text-recette' : 'text-depense')}>
            {balanced ? 'Équilibré' : 'Déséquilibré'}
          </span>
          <span className="text-right font-mono tabular-nums text-ink">
            {formatEUR(totalDebit.toFixed(2))}
          </span>
          <span className="text-right font-mono tabular-nums text-ink">
            {formatEUR(totalCredit.toFixed(2))}
          </span>
          <span />
        </div>
        {lignesError && <p className="text-xs text-depense">{lignesError}</p>}
      </div>

      {/* Advanced, collapsed: reference and payment method. */}
      <div className="border-t border-hairline pt-4">
        <button
          type="button"
          onClick={() => setAdvancedOpen((v) => !v)}
          aria-expanded={advancedOpen}
          className="flex items-center gap-1.5 text-sm font-medium text-ink-soft hover:text-ink"
        >
          <ChevronDown
            className={cn('h-4 w-4 transition-transform', advancedOpen && 'rotate-180')}
            aria-hidden
          />
          Avancé
        </button>
        {advancedOpen && (
          <div className="mt-4 grid gap-5 sm:grid-cols-2">
            <div>
              <Label htmlFor="me-mode">Mode de règlement</Label>
              <Select id="me-mode" className="mt-1.5" {...register('mode_reglement')}>
                <option value="">—</option>
                {MODE_REGLEMENT_VALUES.map((m) => (
                  <option key={m} value={m}>
                    {MODE_REGLEMENT_LABELS[m]}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <Label htmlFor="me-reference">Référence externe</Label>
              <Input
                id="me-reference"
                placeholder="N° de facture…"
                className="mt-1.5"
                {...register('reference_externe')}
              />
              {errors.reference_externe && (
                <p className="mt-1 text-xs text-depense">{errors.reference_externe.message}</p>
              )}
            </div>
          </div>
        )}
      </div>

      {isCorrect && (
        <p className="text-xs text-muted">
          La correction contre-passe l’écriture validée et crée la version corrigée en brouillon
          (l’originale reste inchangée), à valider ensuite.
        </p>
      )}

      {error && <Alert>{error}</Alert>}

      <div className="flex gap-2">
        <Button type="button" variant="ghost" className="flex-1" onClick={onCancel}>
          Annuler
        </Button>
        <Button type="submit" variant="accent" className="flex-1" disabled={busy}>
          {busy
            ? isCorrect
              ? 'Correction…'
              : 'Enregistrement…'
            : isCorrect
              ? 'Corriger l’écriture'
              : 'Enregistrer les modifications'}
        </Button>
      </div>
    </form>
  );
}
