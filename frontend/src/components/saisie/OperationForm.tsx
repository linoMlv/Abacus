import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CheckCircle2, ChevronDown, Paperclip, Plus, X } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useForm } from 'react-hook-form';
import { Link, useParams } from 'react-router-dom';

import {
  accountingApi,
  type Categorie,
  type CompteTresorerie,
  type Ecriture,
  type EcritureContenu,
  type Evenement,
  JUSTIFICATIF_ACCEPT,
  JUSTIFICATIF_MAX_BYTES,
  type LigneEcriture,
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
import { usePermissions } from '@/hooks/usePermissions';
import { formatBytes } from '@/lib/format';
import { PERMISSIONS } from '@/lib/permissions';
import { cn } from '@/lib/utils';

import {
  amountToDecimalString,
  MODE_REGLEMENT_VALUES,
  saisieSchema,
  type SaisieForm,
} from '@/pages/saisie.schema';

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function FieldError({ message }: { message?: string }) {
  if (!message) return null;
  return <p className="mt-1 text-xs text-depense">{message}</p>;
}

/** The named treasury accounts as <option>s (with a placeholder when empty). */
function CompteOptions({ comptes }: { comptes: CompteTresorerie[] }) {
  return (
    <>
      {comptes.length === 0 && <option value="">—</option>}
      {comptes.map((c) => (
        <option key={c.id} value={c.id}>
          {c.libelle}
        </option>
      ))}
    </>
  );
}

/** The total amount of an entry (Σ debit = Σ credit), as a "0.00" string. */
function entryAmount(lignes: LigneEcriture[]): string {
  return lignes.reduce((sum, l) => sum + Number(l.debit), 0).toFixed(2);
}

const BLANK: SaisieForm = {
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
};

export interface OperationFormProps {
  /** ``create`` is the Saisie tab; ``edit`` rebuilds an existing draft in place. */
  mode: 'create' | 'edit';
  /** The draft being edited (required in edit mode). */
  entry?: Ecriture;
  /** Called after a successful edit (e.g. to close the drawer). */
  onSaved?: () => void;
  /** Called when the user cancels an edit. */
  onCancel?: () => void;
}

/**
 * The type-first operation form, shared by creation (Saisie tab) and the inline
 * edition of a draft (journal drawer). In edit mode the type is locked to the
 * entry's origine (a saisie_simple stays recette/dépense, a virement stays a
 * virement — changing origine is not an edit), the fields are pre-filled from the
 * entry, and submitting issues a ``PATCH`` instead of creating a new entry.
 */
export function OperationForm({ mode, entry, onSaved, onCancel }: OperationFormProps) {
  const isEdit = mode === 'edit';
  const { associationId } = useParams() as { associationId: string };
  const { has } = usePermissions();
  const queryClient = useQueryClient();
  const [success, setSuccess] = useState<string | null>(null);
  const [advancedOpen, setAdvancedOpen] = useState(isEdit);

  const canCreate = has(PERMISSIONS.ENTRY_CREATE_SIMPLE);
  const canTransfer = has(PERMISSIONS.ENTRY_CREATE_TRANSFER);
  const canEnter = canCreate || canTransfer;
  const canAddCategorie = has(PERMISSIONS.CATEGORIE_MANAGE);
  const canAddTiers = has(PERMISSIONS.TIERS_MANAGE);
  const canAddEvenement = has(PERMISSIONS.EVENT_MANAGE);
  const canAddJustificatif = has(PERMISSIONS.ATTACHMENT_MANAGE);
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
    enabled: canEnter,
  });
  const comptesQuery = useQuery({
    queryKey: ['tresorerie', associationId],
    queryFn: () => accountingApi.listTresorerie(associationId),
    enabled: canEnter,
  });
  const tiersQuery = useQuery({
    queryKey: ['tiers', associationId],
    queryFn: () => accountingApi.listTiers(associationId),
    enabled: canEnter,
  });
  const evenementsQuery = useQuery({
    queryKey: ['evenements', associationId, 'actif'],
    queryFn: () => accountingApi.listEvenements(associationId, 'actif'),
    enabled: canEnter,
  });

  const form = useForm<SaisieForm>({
    resolver: zodResolver(saisieSchema),
    defaultValues: BLANK,
  });
  const {
    register,
    handleSubmit,
    watch,
    setValue,
    getValues,
    reset,
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

  const typeAllowed = (t: SaisieForm['type']) => {
    if (isEdit) {
      // Editing never changes the origine: a virement stays a virement; a simple
      // entry stays recette/dépense (both map to the same ``simple`` payload).
      return entry?.origine === 'virement' ? t === 'virement' : t !== 'virement';
    }
    return t === 'virement' ? canTransfer : canCreate;
  };

  // Keep the selected category valid as the direction toggles or data loads.
  useEffect(() => {
    if (isVirement) return;
    if (categories.length && !categories.some((c) => c.id === getValues('categorie_id'))) {
      setValue('categorie_id', categories[0].id, { shouldValidate: false });
    }
  }, [isVirement, categories, getValues, setValue]);

  // Default the treasury accounts (create mode): bank (512…) for recette/dépense;
  // for a transfer, a distinct source and destination.
  useEffect(() => {
    if (isEdit || !comptes.length) return;
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
  }, [isEdit, isVirement, comptes, getValues, setValue]);

  // If the current type is not permitted, switch to a permitted one.
  useEffect(() => {
    if (typeAllowed(type)) return;
    if (isEdit) {
      setValue('type', entry?.origine === 'virement' ? 'virement' : 'recette', {
        shouldValidate: false,
      });
    } else {
      setValue('type', canCreate ? 'recette' : 'virement', { shouldValidate: false });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [type, canCreate, canTransfer, isEdit]);

  // Edit mode: once the lookups are loaded, fill the form from the entry once.
  const [prefilled, setPrefilled] = useState(false);
  useEffect(() => {
    if (!isEdit || !entry || prefilled) return;
    if (!categoriesQuery.data || !comptesQuery.data) return;
    const montant = entryAmount(entry.lignes);
    const common: Partial<SaisieForm> = {
      montant,
      date: entry.date,
      libelle: entry.libelle ?? '',
      reference_externe: entry.reference_externe ?? '',
      mode_reglement: entry.mode_reglement ?? '',
    };
    if (entry.origine === 'virement') {
      const debitLine = entry.lignes.find((l) => Number(l.debit) > 0);
      const creditLine = entry.lignes.find((l) => Number(l.credit) > 0);
      reset({
        ...BLANK,
        ...common,
        type: 'virement',
        compte_destination_id: debitLine?.compte_id ?? '',
        compte_source_id: creditLine?.compte_id ?? '',
      });
    } else {
      const treasuryIds = new Set(comptesQuery.data.map((c) => c.id));
      const treasuryLine = entry.lignes.find((l) => treasuryIds.has(l.compte_id));
      const categorie = categoriesQuery.data.find((c) => c.id === entry.categorie_id);
      reset({
        ...BLANK,
        ...common,
        type: categorie?.sens ?? 'recette',
        categorie_id: entry.categorie_id ?? '',
        compte_tresorerie_id: treasuryLine?.compte_id ?? '',
        tiers_id: entry.tiers_id ?? '',
        evenement_id: entry.evenement_id ?? '',
      });
    }
    setPrefilled(true);
  }, [isEdit, entry, prefilled, categoriesQuery.data, comptesQuery.data, reset]);

  function invalidateAfterEntry() {
    queryClient.invalidateQueries({ queryKey: ['ecritures', associationId] });
    queryClient.invalidateQueries({ queryKey: ['balance', associationId] });
    queryClient.invalidateQueries({ queryKey: ['tresorerie', associationId] });
    queryClient.invalidateQueries({ queryKey: ['synthese', associationId] });
  }

  const simpleMutation = useMutation({
    mutationFn: (input: SaisieSimpleInput) => accountingApi.creerSaisieSimple(associationId, input),
  });
  const virementMutation = useMutation({
    mutationFn: (input: VirementInput) => accountingApi.creerVirement(associationId, input),
  });
  const editMutation = useMutation({
    mutationFn: (contenu: EcritureContenu) =>
      accountingApi.modifierEcriture(associationId, entry!.id, contenu),
  });
  const activeMutation = isVirement ? virementMutation : simpleMutation;

  function contenuFor(values: SaisieForm): EcritureContenu {
    const common = {
      montant: amountToDecimalString(values.montant),
      date: values.date,
      libelle: values.libelle?.trim() || undefined,
      reference_externe: values.reference_externe?.trim() || undefined,
      mode_reglement: values.mode_reglement || undefined,
    };
    if (values.type === 'virement') {
      return {
        virement: {
          compte_source_id: values.compte_source_id,
          compte_destination_id: values.compte_destination_id,
          ...common,
        },
      };
    }
    return {
      simple: {
        categorie_id: values.categorie_id,
        compte_tresorerie_id: values.compte_tresorerie_id,
        tiers_id: values.tiers_id || undefined,
        evenement_id: values.evenement_id || undefined,
        ...common,
      },
    };
  }

  const onSubmit = handleSubmit(async (values) => {
    if (isEdit) {
      setBusy(true);
      try {
        await editMutation.mutateAsync(contenuFor(values));
        invalidateAfterEntry();
        queryClient.invalidateQueries({ queryKey: ['ecriture', associationId, entry!.id] });
        onSaved?.();
      } catch {
        // editMutation's error state drives the Alert below.
      } finally {
        setBusy(false);
      }
      return;
    }

    setSuccess(null);
    setBusy(true);
    const contenu = contenuFor(values);
    try {
      const ecriture = contenu.virement
        ? await virementMutation.mutateAsync(contenu.virement)
        : await simpleMutation.mutateAsync(contenu.simple!);

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
      queryClient.invalidateQueries({ queryKey: ['justificatifs', associationId, ecriture.id] });

      const label = values.type === 'virement' ? 'Virement' : 'Écriture';
      const ending = values.type === 'virement' ? '' : 'e';
      const joined = pendingFiles.length - failed;
      let message = `${label} n° ${ecriture.numero_piece} enregistré${ending}.`;
      if (joined > 0) message += ` ${joined} justificatif(s) joint(s).`;
      if (failed > 0) message += ` ${failed} justificatif(s) non envoyé(s).`;
      setSuccess(message);
      setPendingFiles([]);
      setFileError(null);
      reset({ ...getValues(), montant: '', libelle: '', reference_externe: '' });
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
    if (next === type || !typeAllowed(next)) return;
    setSuccess(null);
    setValue('type', next);
  }

  function onCategorieCreated(cat: Categorie) {
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

  if (!canEnter) {
    return (
      <Card className="p-6 text-sm text-muted">
        Vous n’avez pas l’autorisation de saisir des opérations.
      </Card>
    );
  }

  const error = isEdit
    ? apiErrorMessage(editMutation, 'Modification impossible.')
    : apiErrorMessage(activeMutation, 'Enregistrement impossible.');
  const loadError = categoriesQuery.isError || comptesQuery.isError;
  const quickAddSens = type === 'depense' ? 'depense' : 'recette';

  const core = (
    <>
      {/* Operation type — the only "accounting" concept a volunteer sees. */}
      <div className="grid grid-cols-3 gap-2" role="group" aria-label="Type d’opération">
        <TypeButton
          active={type === 'recette'}
          tone="recette"
          label="Recette"
          hint="Argent reçu"
          disabled={!typeAllowed('recette')}
          onClick={() => selectType('recette')}
        />
        <TypeButton
          active={type === 'depense'}
          tone="depense"
          label="Dépense"
          hint="Argent versé"
          disabled={!typeAllowed('depense')}
          onClick={() => selectType('depense')}
        />
        <TypeButton
          active={type === 'virement'}
          tone="neutre"
          label="Virement"
          hint="Entre comptes"
          disabled={!typeAllowed('virement')}
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
                <CompteOptions comptes={comptes} />
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
                <CompteOptions comptes={comptes} />
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
              <CompteOptions comptes={comptes} />
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

              {!isEdit && canAddJustificatif && (
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
              {isEdit && (
                <p className="text-xs text-faint">
                  Les justificatifs se gèrent depuis le détail de l’écriture.
                </p>
              )}
            </div>
          )}
        </div>

        {error && <Alert>{error}</Alert>}
        {!isEdit && success && (
          <div
            role="status"
            className="flex items-center gap-2 rounded-lg border border-recette/20 bg-recette-soft px-3.5 py-2.5 text-sm text-recette"
          >
            <CheckCircle2 className="h-4 w-4" aria-hidden />
            {success}
          </div>
        )}

        {isEdit ? (
          <div className="flex gap-2">
            <Button type="button" variant="ghost" className="flex-1" onClick={onCancel}>
              Annuler
            </Button>
            <Button type="submit" variant="accent" className="flex-1" disabled={busy}>
              {busy ? 'Enregistrement…' : 'Enregistrer les modifications'}
            </Button>
          </div>
        ) : (
          <Button
            type="submit"
            variant="accent"
            className="w-full"
            disabled={busy || !typeAllowed(type)}
          >
            {busy
              ? 'Enregistrement…'
              : isVirement
                ? 'Enregistrer le virement'
                : 'Enregistrer l’opération'}
          </Button>
        )}
      </form>
    </>
  );

  const dialogs = (
    <>
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
    </>
  );

  if (isEdit) {
    return (
      <div>
        {core}
        {dialogs}
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl">
      <Card className="p-6">{core}</Card>

      <p className="mt-3 text-center text-xs text-faint">
        {isVirement
          ? 'Le virement déplace l’argent entre vos comptes, sans impact sur le résultat.'
          : 'Abacus génère l’écriture en partie double automatiquement.'}
        {canAddCategorie && !isVirement && (
          <>
            {' · '}
            <Link
              to={`/asso/${associationId}/saisie?tab=categories`}
              className="text-accent hover:text-accent-hover"
            >
              Gérer les catégories
            </Link>
          </>
        )}
      </p>

      {dialogs}
    </div>
  );
}

function TypeButton({
  active,
  tone,
  label,
  hint,
  disabled,
  onClick,
}: {
  active: boolean;
  tone: 'recette' | 'depense' | 'neutre';
  label: string;
  hint: string;
  disabled?: boolean;
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
      disabled={disabled}
      title={disabled ? 'Action non autorisée' : undefined}
      onClick={onClick}
      className={cn(
        'rounded-lg border px-4 py-3 text-left transition-colors',
        active ? activeRing : 'border-hairline bg-surface text-ink-soft hover:bg-hover',
        disabled && 'cursor-not-allowed opacity-50 hover:bg-surface'
      )}
    >
      <span className="block text-sm font-semibold">{label}</span>
      <span className="block text-xs opacity-80">{hint}</span>
    </button>
  );
}
