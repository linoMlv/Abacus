import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CheckCircle2 } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useForm } from 'react-hook-form';
import { useParams } from 'react-router-dom';

import { accountingApi, CLASSE_TRESORERIE, type SaisieSimpleInput } from '@/api/accounting';
import { apiErrorMessage } from '@/api/client';
import { Alert } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import { useActiveAssociation } from '@/hooks/useActiveAssociation';
import { cn } from '@/lib/utils';
import { canCreateSimpleEntry } from '@/lib/roles';

import { amountToDecimalString, saisieSchema, type SaisieForm } from './saisie.schema';

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

/** Inline validation message under a field. */
function FieldError({ message }: { message?: string }) {
  if (!message) return null;
  return <p className="mt-1 text-xs text-depense">{message}</p>;
}

export function SaisiePage() {
  const { associationId } = useParams() as { associationId: string };
  const association = useActiveAssociation();
  const queryClient = useQueryClient();
  const [success, setSuccess] = useState<string | null>(null);

  const canCreate = association ? canCreateSimpleEntry(association.role) : false;

  const categoriesQuery = useQuery({
    queryKey: ['categories', associationId],
    queryFn: () => accountingApi.listCategories(associationId),
    enabled: canCreate,
  });
  const comptesQuery = useQuery({
    queryKey: ['comptes', associationId, CLASSE_TRESORERIE],
    queryFn: () => accountingApi.listComptes(associationId, CLASSE_TRESORERIE),
    enabled: canCreate,
  });

  const form = useForm<SaisieForm>({
    resolver: zodResolver(saisieSchema),
    defaultValues: {
      sens: 'recette',
      categorie_id: '',
      compte_tresorerie_id: '',
      montant: '',
      date: today(),
      libelle: '',
    },
  });
  const {
    register,
    handleSubmit,
    watch,
    setValue,
    getValues,
    formState: { errors },
  } = form;
  const sens = watch('sens');

  const categories = useMemo(
    () => (categoriesQuery.data ?? []).filter((c) => c.sens === sens),
    [categoriesQuery.data, sens]
  );
  const comptes = useMemo(() => comptesQuery.data ?? [], [comptesQuery.data]);

  // Keep the selected category valid as the direction toggles or data loads.
  useEffect(() => {
    if (categories.length && !categories.some((c) => c.id === getValues('categorie_id'))) {
      setValue('categorie_id', categories[0].id, { shouldValidate: false });
    }
  }, [categories, getValues, setValue]);

  // Default the counterpart to the bank account (512…), else the first one.
  useEffect(() => {
    if (comptes.length && !getValues('compte_tresorerie_id')) {
      const prefer = comptes.find((c) => c.numero.startsWith('512')) ?? comptes[0];
      setValue('compte_tresorerie_id', prefer.id, { shouldValidate: false });
    }
  }, [comptes, getValues, setValue]);

  const mutation = useMutation({
    mutationFn: (input: SaisieSimpleInput) => accountingApi.creerSaisieSimple(associationId, input),
    onSuccess: (ecriture) => {
      setSuccess(`Écriture n° ${ecriture.numero_piece} enregistrée.`);
      // Keep direction/category/account/date for fast repeat entry.
      form.reset({ ...getValues(), montant: '', libelle: '' });
      queryClient.invalidateQueries({ queryKey: ['ecritures', associationId] });
      queryClient.invalidateQueries({ queryKey: ['balance', associationId] });
    },
  });

  const onSubmit = handleSubmit((values) => {
    setSuccess(null);
    mutation.mutate({
      categorie_id: values.categorie_id,
      compte_tresorerie_id: values.compte_tresorerie_id,
      montant: amountToDecimalString(values.montant),
      date: values.date,
      libelle: values.libelle?.trim() || undefined,
    });
  });

  function selectSens(next: SaisieForm['sens']) {
    if (next === sens) return;
    setSuccess(null);
    setValue('sens', next);
  }

  if (!canCreate) {
    return (
      <div className="mx-auto max-w-2xl">
        <Header />
        <Card className="mt-6 p-6 text-sm text-muted">
          Votre rôle est en consultation seule : la saisie d’opérations n’est pas disponible.
        </Card>
      </div>
    );
  }

  const error = apiErrorMessage(mutation, 'Enregistrement impossible.');
  const loadError = categoriesQuery.isError || comptesQuery.isError;

  return (
    <div className="mx-auto max-w-2xl">
      <Header />

      <Card className="mt-6 p-6">
        {/* Direction toggle — the only "accounting" concept a volunteer sees. */}
        <div className="grid grid-cols-2 gap-2" role="group" aria-label="Sens de l’opération">
          <SensButton
            active={sens === 'recette'}
            tone="recette"
            label="Recette"
            hint="Argent reçu"
            onClick={() => selectSens('recette')}
          />
          <SensButton
            active={sens === 'depense'}
            tone="depense"
            label="Dépense"
            hint="Argent versé"
            onClick={() => selectSens('depense')}
          />
        </div>

        {loadError && (
          <Alert className="mt-5">Impossible de charger les catégories ou les comptes.</Alert>
        )}

        <form onSubmit={onSubmit} className="mt-5 space-y-5" noValidate>
          <div>
            <Label htmlFor="categorie_id">Catégorie</Label>
            <Select id="categorie_id" className="mt-1.5" {...register('categorie_id')}>
              {categories.length === 0 && <option value="">—</option>}
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.libelle}
                </option>
              ))}
            </Select>
            <FieldError message={errors.categorie_id?.message} />
          </div>

          <div className="grid gap-5 sm:grid-cols-2">
            <div>
              <Label htmlFor="montant">Montant (€)</Label>
              <Input
                id="montant"
                inputMode="decimal"
                placeholder="0,00"
                className="mt-1.5 text-right font-mono tabular-nums"
                {...register('montant')}
              />
              <FieldError message={errors.montant?.message} />
            </div>
            <div>
              <Label htmlFor="date">Date</Label>
              <Input id="date" type="date" className="mt-1.5" {...register('date')} />
              <FieldError message={errors.date?.message} />
            </div>
          </div>

          <div>
            <Label htmlFor="compte_tresorerie_id">Compte de trésorerie</Label>
            <Select
              id="compte_tresorerie_id"
              className="mt-1.5"
              {...register('compte_tresorerie_id')}
            >
              {comptes.length === 0 && <option value="">—</option>}
              {comptes.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.numero} — {c.libelle}
                </option>
              ))}
            </Select>
            <FieldError message={errors.compte_tresorerie_id?.message} />
          </div>

          <div>
            <Label htmlFor="libelle">Libellé (optionnel)</Label>
            <Input
              id="libelle"
              placeholder="Repris de la catégorie si vide"
              className="mt-1.5"
              {...register('libelle')}
            />
            <FieldError message={errors.libelle?.message} />
          </div>

          {error && <Alert>{error}</Alert>}
          {success && (
            <div
              role="status"
              className="flex items-center gap-2 rounded-lg border border-recette/20 bg-recette-soft px-3.5 py-2.5 text-sm text-recette"
            >
              <CheckCircle2 className="h-4 w-4" aria-hidden />
              {success}
            </div>
          )}

          <Button type="submit" variant="accent" className="w-full" disabled={mutation.isPending}>
            {mutation.isPending ? 'Enregistrement…' : 'Enregistrer l’opération'}
          </Button>
        </form>
      </Card>

      <p className="mt-3 text-center text-xs text-faint">
        Abacus génère l’écriture en partie double automatiquement.
      </p>
    </div>
  );
}

function Header() {
  return (
    <div>
      <h2 className="text-xl font-semibold tracking-tight text-ink">Saisie</h2>
      <p className="mt-1 text-sm text-muted">
        Enregistrez une recette ou une dépense ; la comptabilité suit toute seule.
      </p>
    </div>
  );
}

function SensButton({
  active,
  tone,
  label,
  hint,
  onClick,
}: {
  active: boolean;
  tone: 'recette' | 'depense';
  label: string;
  hint: string;
  onClick: () => void;
}) {
  const activeRing =
    tone === 'recette'
      ? 'border-recette bg-recette-soft text-recette'
      : 'border-depense bg-depense-soft text-depense';
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={cn(
        'rounded-lg border px-4 py-3 text-left transition-colors',
        active ? activeRing : 'border-hairline bg-surface text-ink-soft hover:bg-hover'
      )}
    >
      <span className="block text-sm font-semibold">{label}</span>
      <span className="block text-xs opacity-80">{hint}</span>
    </button>
  );
}
