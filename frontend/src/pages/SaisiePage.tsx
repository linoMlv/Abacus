import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CheckCircle2, ChevronDown, Paperclip, Plus, X } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useForm } from 'react-hook-form';
import { Link, useParams } from 'react-router-dom';

import {
  accountingApi,
  type Categorie,
  type Evenement,
  JUSTIFICATIF_ACCEPT,
  JUSTIFICATIF_MAX_BYTES,
  MODE_REGLEMENT_LABELS,
  type SaisieSimpleInput,
  type Tiers,
  type VirementInput,
} from '@/api/accounting';
import { apiErrorMessage } from '@/api/client';
import { CategorieDialog } from '@/components/CategorieDialog';
import { EvenementDialog } from '@/components/EvenementDialog';
import { TiersDialog } from '@/components/TiersDialog';
import { Alert } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import { useActiveAssociation } from '@/hooks/useActiveAssociation';
import { formatBytes } from '@/lib/format';
import {
  canCreateSimpleEntry,
  canManageAttachment,
  canManageCategorie,
  canManageEvenement,
  canManageTiers,
} from '@/lib/roles';
import { cn } from '@/lib/utils';

import {
  amountToDecimalString,
  MODE_REGLEMENT_VALUES,
  saisieSchema,
  type SaisieForm,
} from './saisie.schema';

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
  const [advancedOpen, setAdvancedOpen] = useState(false);

  const canCreate = association ? canCreateSimpleEntry(association.role) : false;
  const canAddCategorie = association ? canManageCategorie(association.role) : false;
  const canAddTiers = association ? canManageTiers(association.role) : false;
  const canAddEvenement = association ? canManageEvenement(association.role) : false;
  const canAddJustificatif = association ? canManageAttachment(association.role) : false;
  const [catDialogOpen, setCatDialogOpen] = useState(false);
  const [tiersDialogOpen, setTiersDialogOpen] = useState(false);
  const [evenementDialogOpen, setEvenementDialogOpen] = useState(false);
  const [pendingFiles, setPendingFiles] = useState<File[]>([]);
  const [fileError, setFileError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const categoriesQuery = useQuery({
    queryKey: ['categories', associationId],
    queryFn: () => accountingApi.listCategories(associationId),
    enabled: canCreate,
  });
  const comptesQuery = useQuery({
    queryKey: ['tresorerie', associationId],
    queryFn: () => accountingApi.listTresorerie(associationId),
    enabled: canCreate,
  });
  const tiersQuery = useQuery({
    queryKey: ['tiers', associationId],
    queryFn: () => accountingApi.listTiers(associationId),
    enabled: canCreate,
  });
  const evenementsQuery = useQuery({
    queryKey: ['evenements', associationId, 'actif'],
    queryFn: () => accountingApi.listEvenements(associationId, 'actif'),
    enabled: canCreate,
  });

  const form = useForm<SaisieForm>({
    resolver: zodResolver(saisieSchema),
    defaultValues: {
      type: 'recette',
      categorie_id: '',
      compte_tresorerie_id: '',
      compte_source_id: '',
      compte_destination_id: '',
      montant: '',
      date: today(),
      tiers_id: '',
      evenement_id: '',
      libelle: '',
      reference_externe: '',
      mode_reglement: '',
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
  const type = watch('type');
  const isVirement = type === 'virement';

  const categories = useMemo(
    () => (categoriesQuery.data ?? []).filter((c) => c.sens === type),
    [categoriesQuery.data, type]
  );
  const comptes = useMemo(() => comptesQuery.data ?? [], [comptesQuery.data]);
  const tiersList = useMemo(() => tiersQuery.data ?? [], [tiersQuery.data]);
  const evenementsList = useMemo(() => evenementsQuery.data ?? [], [evenementsQuery.data]);

  // Keep the selected category valid as the direction toggles or data loads.
  useEffect(() => {
    if (isVirement) return;
    if (categories.length && !categories.some((c) => c.id === getValues('categorie_id'))) {
      setValue('categorie_id', categories[0].id, { shouldValidate: false });
    }
  }, [isVirement, categories, getValues, setValue]);

  // Default the treasury accounts: bank (512…) for recette/dépense; for a
  // transfer, a distinct source and destination.
  useEffect(() => {
    if (!comptes.length) return;
    const bank = comptes.find((c) => c.numero.startsWith('512')) ?? comptes[0];
    if (!isVirement) {
      if (!getValues('compte_tresorerie_id')) {
        setValue('compte_tresorerie_id', bank.id, { shouldValidate: false });
      }
      return;
    }
    if (!getValues('compte_source_id')) {
      const source = comptes.find((c) => c.id !== bank.id) ?? comptes[0];
      setValue('compte_source_id', source.id, { shouldValidate: false });
    }
    if (!getValues('compte_destination_id')) {
      setValue('compte_destination_id', bank.id, { shouldValidate: false });
    }
  }, [isVirement, comptes, getValues, setValue]);

  function invalidateAfterEntry() {
    queryClient.invalidateQueries({ queryKey: ['ecritures', associationId] });
    queryClient.invalidateQueries({ queryKey: ['balance', associationId] });
    queryClient.invalidateQueries({ queryKey: ['tresorerie', associationId] });
  }

  const simpleMutation = useMutation({
    mutationFn: (input: SaisieSimpleInput) => accountingApi.creerSaisieSimple(associationId, input),
  });
  const virementMutation = useMutation({
    mutationFn: (input: VirementInput) => accountingApi.creerVirement(associationId, input),
  });
  const activeMutation = isVirement ? virementMutation : simpleMutation;

  const onSubmit = handleSubmit(async (values) => {
    setSuccess(null);
    setBusy(true);
    const common = {
      montant: amountToDecimalString(values.montant),
      date: values.date,
      libelle: values.libelle?.trim() || undefined,
      reference_externe: values.reference_externe?.trim() || undefined,
      mode_reglement: values.mode_reglement || undefined,
    };
    try {
      const ecriture =
        values.type === 'virement'
          ? await virementMutation.mutateAsync({
              compte_source_id: values.compte_source_id,
              compte_destination_id: values.compte_destination_id,
              ...common,
            })
          : await simpleMutation.mutateAsync({
              categorie_id: values.categorie_id,
              compte_tresorerie_id: values.compte_tresorerie_id,
              tiers_id: values.tiers_id || undefined,
              evenement_id: values.evenement_id || undefined,
              ...common,
            });

      // The entry now exists: attach the chosen files to it.
      let failed = 0;
      for (const file of pendingFiles) {
        try {
          await accountingApi.uploadJustificatif(associationId, ecriture.id, file);
        } catch {
          failed += 1;
        }
      }
      invalidateAfterEntry();
      queryClient.invalidateQueries({
        queryKey: ['justificatifs', associationId, ecriture.id],
      });

      const label = values.type === 'virement' ? 'Virement' : 'Écriture';
      const ending = values.type === 'virement' ? '' : 'e';
      const joined = pendingFiles.length - failed;
      let message = `${label} n° ${ecriture.numero_piece} enregistré${ending}.`;
      if (joined > 0) message += ` ${joined} justificatif(s) joint(s).`;
      if (failed > 0) message += ` ${failed} justificatif(s) non envoyé(s).`;
      setSuccess(message);
      setPendingFiles([]);
      setFileError(null);
      form.reset({ ...getValues(), montant: '', libelle: '', reference_externe: '' });
    } catch {
      // The create mutation's error state drives the Alert below.
    } finally {
      setBusy(false);
    }
  });

  function onPickFiles(e: React.ChangeEvent<HTMLInputElement>) {
    const chosen = Array.from(e.target.files ?? []);
    e.target.value = ''; // allow re-picking the same file
    const accepted = chosen.filter((f) => f.size <= JUSTIFICATIF_MAX_BYTES);
    setFileError(
      accepted.length < chosen.length
        ? 'Certains fichiers dépassent 5 Mo et ont été ignorés.'
        : null
    );
    if (accepted.length) setPendingFiles((prev) => [...prev, ...accepted]);
  }

  function removePendingFile(index: number) {
    setPendingFiles((prev) => prev.filter((_, i) => i !== index));
  }

  function selectType(next: SaisieForm['type']) {
    if (next === type) return;
    setSuccess(null);
    setValue('type', next);
  }

  function onCategorieCreated(cat: Categorie) {
    // Surface the new category immediately, then select it (the invalidation
    // triggered by the dialog reconciles with the server list).
    queryClient.setQueryData<Categorie[]>(['categories', associationId], (old) =>
      old ? [...old, cat] : [cat]
    );
    setValue('categorie_id', cat.id, { shouldValidate: true });
  }

  function onTiersCreated(tiers: Tiers) {
    queryClient.setQueryData<Tiers[]>(['tiers', associationId], (old) =>
      old ? [...old, tiers] : [tiers]
    );
    setValue('tiers_id', tiers.id, { shouldValidate: false });
  }

  function onEvenementCreated(evenement: Evenement) {
    queryClient.setQueryData<Evenement[]>(['evenements', associationId, 'actif'], (old) =>
      old ? [...old, evenement] : [evenement]
    );
    setValue('evenement_id', evenement.id, { shouldValidate: false });
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

  const error = apiErrorMessage(activeMutation, 'Enregistrement impossible.');
  const loadError = categoriesQuery.isError || comptesQuery.isError;
  const quickAddSens = type === 'depense' ? 'depense' : 'recette';

  return (
    <div className="mx-auto max-w-2xl">
      <Header />

      <Card className="mt-6 p-6">
        {/* Operation type — the only "accounting" concept a volunteer sees. */}
        <div className="grid grid-cols-3 gap-2" role="group" aria-label="Type d’opération">
          <TypeButton
            active={type === 'recette'}
            tone="recette"
            label="Recette"
            hint="Argent reçu"
            onClick={() => selectType('recette')}
          />
          <TypeButton
            active={type === 'depense'}
            tone="depense"
            label="Dépense"
            hint="Argent versé"
            onClick={() => selectType('depense')}
          />
          <TypeButton
            active={type === 'virement'}
            tone="neutre"
            label="Virement"
            hint="Entre comptes"
            onClick={() => selectType('virement')}
          />
        </div>

        {loadError && (
          <Alert className="mt-5">Impossible de charger les catégories ou les comptes.</Alert>
        )}

        <form onSubmit={onSubmit} className="mt-5 space-y-5" noValidate>
          {isVirement ? (
            <div className="grid gap-5 sm:grid-cols-2">
              <div>
                <Label htmlFor="compte_source_id">Compte de départ</Label>
                <Select id="compte_source_id" className="mt-1.5" {...register('compte_source_id')}>
                  {comptes.length === 0 && <option value="">—</option>}
                  {comptes.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.libelle}
                    </option>
                  ))}
                </Select>
                <FieldError message={errors.compte_source_id?.message} />
              </div>
              <div>
                <Label htmlFor="compte_destination_id">Compte d’arrivée</Label>
                <Select
                  id="compte_destination_id"
                  className="mt-1.5"
                  {...register('compte_destination_id')}
                >
                  {comptes.length === 0 && <option value="">—</option>}
                  {comptes.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.libelle}
                    </option>
                  ))}
                </Select>
                <FieldError message={errors.compte_destination_id?.message} />
              </div>
            </div>
          ) : (
            <div>
              <div className="flex items-center justify-between">
                <Label htmlFor="categorie_id">Catégorie</Label>
                {canAddCategorie && (
                  <button
                    type="button"
                    onClick={() => setCatDialogOpen(true)}
                    className="inline-flex items-center gap-1 text-xs font-medium text-accent hover:text-accent-hover"
                  >
                    <Plus className="h-3.5 w-3.5" aria-hidden />
                    Nouvelle
                  </button>
                )}
              </div>
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
          )}

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

          {!isVirement && (
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
                    {c.libelle}
                  </option>
                ))}
              </Select>
              <FieldError message={errors.compte_tresorerie_id?.message} />
            </div>
          )}

          {/* Advanced, collapsed by default: simple by default, powerful on demand. */}
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
              <div className="mt-4 space-y-5">
                {!isVirement && (
                  <div>
                    <div className="flex items-center justify-between">
                      <Label htmlFor="tiers_id">Tiers</Label>
                      {canAddTiers && (
                        <button
                          type="button"
                          aria-label="Nouveau tiers"
                          onClick={() => setTiersDialogOpen(true)}
                          className="inline-flex items-center gap-1 text-xs font-medium text-accent hover:text-accent-hover"
                        >
                          <Plus className="h-3.5 w-3.5" aria-hidden />
                          Nouveau
                        </button>
                      )}
                    </div>
                    <Select id="tiers_id" className="mt-1.5" {...register('tiers_id')}>
                      <option value="">— Aucun</option>
                      {tiersList.map((t) => (
                        <option key={t.id} value={t.id}>
                          {t.nom}
                        </option>
                      ))}
                    </Select>
                  </div>
                )}
                {!isVirement && (
                  <div>
                    <div className="flex items-center justify-between">
                      <Label htmlFor="evenement_id">Événement</Label>
                      {canAddEvenement && (
                        <button
                          type="button"
                          aria-label="Nouvel événement"
                          onClick={() => setEvenementDialogOpen(true)}
                          className="inline-flex items-center gap-1 text-xs font-medium text-accent hover:text-accent-hover"
                        >
                          <Plus className="h-3.5 w-3.5" aria-hidden />
                          Nouveau
                        </button>
                      )}
                    </div>
                    <Select id="evenement_id" className="mt-1.5" {...register('evenement_id')}>
                      <option value="">— Aucun</option>
                      {evenementsList.map((e) => (
                        <option key={e.id} value={e.id}>
                          {e.nom}
                        </option>
                      ))}
                    </Select>
                  </div>
                )}
                <div>
                  <Label htmlFor="libelle">Libellé</Label>
                  <Input
                    id="libelle"
                    placeholder={
                      isVirement ? 'Repris des comptes si vide' : 'Repris de la catégorie si vide'
                    }
                    className="mt-1.5"
                    {...register('libelle')}
                  />
                  <FieldError message={errors.libelle?.message} />
                </div>
                <div className="grid gap-5 sm:grid-cols-2">
                  <div>
                    <Label htmlFor="mode_reglement">Mode de règlement</Label>
                    <Select id="mode_reglement" className="mt-1.5" {...register('mode_reglement')}>
                      <option value="">—</option>
                      {MODE_REGLEMENT_VALUES.map((m) => (
                        <option key={m} value={m}>
                          {MODE_REGLEMENT_LABELS[m]}
                        </option>
                      ))}
                    </Select>
                  </div>
                  <div>
                    <Label htmlFor="reference_externe">Référence externe</Label>
                    <Input
                      id="reference_externe"
                      placeholder="N° de facture, de chèque…"
                      className="mt-1.5"
                      {...register('reference_externe')}
                    />
                    <FieldError message={errors.reference_externe?.message} />
                  </div>
                </div>

                {canAddJustificatif && (
                  <div>
                    <div className="flex items-center justify-between">
                      <Label htmlFor="justificatifs">Justificatifs</Label>
                      <button
                        type="button"
                        onClick={() => fileInputRef.current?.click()}
                        className="inline-flex items-center gap-1 text-xs font-medium text-accent hover:text-accent-hover"
                      >
                        <Paperclip className="h-3.5 w-3.5" aria-hidden />
                        Joindre un fichier
                      </button>
                    </div>
                    <input
                      ref={fileInputRef}
                      id="justificatifs"
                      type="file"
                      multiple
                      accept={JUSTIFICATIF_ACCEPT}
                      className="sr-only"
                      onChange={onPickFiles}
                      aria-label="Joindre des justificatifs"
                    />
                    {pendingFiles.length === 0 ? (
                      <p className="mt-1.5 text-xs text-muted">
                        PDF ou image, 5 Mo max. Joints après l’enregistrement.
                      </p>
                    ) : (
                      <ul className="mt-2 space-y-1.5">
                        {pendingFiles.map((file, index) => (
                          <li
                            key={`${file.name}-${index}`}
                            className="flex items-center gap-2 rounded-lg border border-hairline px-3 py-1.5 text-sm"
                          >
                            <span className="min-w-0 flex-1 truncate text-ink">{file.name}</span>
                            <span className="shrink-0 text-xs text-faint">
                              {formatBytes(file.size)}
                            </span>
                            <button
                              type="button"
                              onClick={() => removePendingFile(index)}
                              className="shrink-0 rounded-md p-1 text-faint hover:bg-hover hover:text-depense"
                              aria-label={`Retirer ${file.name}`}
                            >
                              <X className="h-4 w-4" aria-hidden />
                            </button>
                          </li>
                        ))}
                      </ul>
                    )}
                    {fileError && <p className="mt-1.5 text-xs text-depense">{fileError}</p>}
                  </div>
                )}
              </div>
            )}
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

          <Button type="submit" variant="accent" className="w-full" disabled={busy}>
            {busy
              ? 'Enregistrement…'
              : isVirement
                ? 'Enregistrer le virement'
                : 'Enregistrer l’opération'}
          </Button>
        </form>
      </Card>

      <p className="mt-3 text-center text-xs text-faint">
        {isVirement
          ? 'Le virement déplace l’argent entre vos comptes, sans impact sur le résultat.'
          : 'Abacus génère l’écriture en partie double automatiquement.'}
        {canAddCategorie && !isVirement && (
          <>
            {' · '}
            <Link
              to={`/asso/${associationId}/categories`}
              className="text-accent hover:text-accent-hover"
            >
              Gérer les catégories
            </Link>
          </>
        )}
      </p>

      {canAddCategorie && (
        <CategorieDialog
          associationId={associationId}
          defaultSens={quickAddSens}
          open={catDialogOpen}
          onOpenChange={setCatDialogOpen}
          onSaved={onCategorieCreated}
        />
      )}

      {canAddTiers && (
        <TiersDialog
          associationId={associationId}
          defaultType={type === 'recette' ? 'donateur' : 'fournisseur'}
          open={tiersDialogOpen}
          onOpenChange={setTiersDialogOpen}
          onSaved={onTiersCreated}
        />
      )}

      {canAddEvenement && (
        <EvenementDialog
          associationId={associationId}
          evenement={null}
          open={evenementDialogOpen}
          onOpenChange={setEvenementDialogOpen}
          onSaved={onEvenementCreated}
        />
      )}
    </div>
  );
}

function Header() {
  return (
    <div>
      <h2 className="text-xl font-semibold tracking-tight text-ink">Saisie</h2>
      <p className="mt-1 text-sm text-muted">
        Enregistrez une recette, une dépense ou un virement ; la comptabilité suit toute seule.
      </p>
    </div>
  );
}

function TypeButton({
  active,
  tone,
  label,
  hint,
  onClick,
}: {
  active: boolean;
  tone: 'recette' | 'depense' | 'neutre';
  label: string;
  hint: string;
  onClick: () => void;
}) {
  const activeRing = {
    recette: 'border-recette bg-recette-soft text-recette',
    depense: 'border-depense bg-depense-soft text-depense',
    neutre: 'border-accent bg-accent-soft text-accent',
  }[tone];
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
