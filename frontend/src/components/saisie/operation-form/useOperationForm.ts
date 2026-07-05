import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useForm } from 'react-hook-form';
import { useParams } from 'react-router-dom';

import {
  accountingApi,
  type Categorie,
  type Ecriture,
  type EcritureContenu,
  type Evenement,
  JUSTIFICATIF_MAX_BYTES,
  type SaisieSimpleInput,
  type Sens,
  type Tiers,
  type VirementInput,
} from '@/api/accounting';
import { apiErrorMessage } from '@/api/client';
import { usePermissions } from '@/hooks/usePermissions';
import { useRegimeTva } from '@/hooks/useRegimeTva';
import { PERMISSIONS } from '@/lib/permissions';
import { normalizeTaux } from '@/lib/tva';
import { amountToDecimalString, saisieSchema, type SaisieForm } from '@/pages/saisie.schema';

import { entryAmount, entryTvaTaux, today } from './helpers';

export type OperationMode = 'create' | 'edit' | 'correct';

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
  tva_taux: '0',
};

interface UseOperationFormArgs {
  mode: OperationMode;
  entry?: Ecriture;
  onSaved?: () => void;
}

/** All state, data, effects and mutations behind the type-first operation form. */
export function useOperationForm({ mode, entry, onSaved }: UseOperationFormArgs) {
  const isCreate = mode === 'create';
  const isCorrect = mode === 'correct';
  // edit and correct both pre-fill from, and lock to, an existing entry.
  const fromEntry = !isCreate;
  const { associationId } = useParams() as { associationId: string };
  const { has } = usePermissions();
  const regimeTva = useRegimeTva();
  const queryClient = useQueryClient();
  const [success, setSuccess] = useState<string | null>(null);
  const [advancedOpen, setAdvancedOpen] = useState(fromEntry);

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
  const categorieId = watch('categorie_id');
  const isVirement = type === 'virement';

  const categories = useMemo(
    () => (categoriesQuery.data ?? []).filter((c) => c.sens === type),
    [categoriesQuery.data, type]
  );
  const comptes = useMemo(() => comptesQuery.data ?? [], [comptesQuery.data]);
  const tiersList = useMemo(() => tiersQuery.data ?? [], [tiersQuery.data]);
  const evenementsList = useMemo(() => evenementsQuery.data ?? [], [evenementsQuery.data]);

  const typeAllowed = (t: SaisieForm['type']) => {
    if (fromEntry) {
      // Editing/correcting never changes the origine: a virement stays a virement;
      // a simple entry stays recette/dépense (both map to the same ``simple`` payload).
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

  // Default the VAT rate to the chosen category's default when it changes
  // (create mode, régime on); the user can still override it in Avancé.
  const prevCatRef = useRef('');
  useEffect(() => {
    if (fromEntry || !regimeTva || isVirement || !categorieId) return;
    if (categorieId === prevCatRef.current) return;
    prevCatRef.current = categorieId;
    const cat = categories.find((c) => c.id === categorieId);
    setValue('tva_taux', normalizeTaux(cat?.tva_taux), { shouldValidate: false });
  }, [categorieId, categories, regimeTva, isVirement, fromEntry, setValue]);

  // Default the treasury accounts (create mode): bank (512…) for recette/dépense;
  // for a transfer, a distinct source and destination.
  useEffect(() => {
    if (fromEntry || !comptes.length) return;
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
  }, [fromEntry, isVirement, comptes, getValues, setValue]);

  // If the current type is not permitted, switch to a permitted one.
  useEffect(() => {
    if (typeAllowed(type)) return;
    if (fromEntry) {
      setValue('type', entry?.origine === 'virement' ? 'virement' : 'recette', {
        shouldValidate: false,
      });
    } else {
      setValue('type', canCreate ? 'recette' : 'virement', { shouldValidate: false });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [type, canCreate, canTransfer, fromEntry]);

  // Edit/correct mode: once the lookups are loaded, fill the form from the entry once.
  const [prefilled, setPrefilled] = useState(false);
  useEffect(() => {
    if (!fromEntry || !entry || prefilled) return;
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
        tva_taux: entryTvaTaux(entry.lignes),
      });
    }
    setPrefilled(true);
  }, [fromEntry, entry, prefilled, categoriesQuery.data, comptesQuery.data, reset]);

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
  // Correct a validated entry: contre-passe it and book the corrected draft in one
  // call (annule-et-remplace); the original stays immutable (ANC §10).
  const correctMutation = useMutation({
    mutationFn: (contenu: EcritureContenu) =>
      accountingApi.contrepasserEcriture(associationId, entry!.id, { remplacement: contenu }),
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
        // Only send a rate when the régime is on; the server masks it otherwise.
        tva_taux: regimeTva ? (values.tva_taux ?? '0') : undefined,
        ...common,
      },
    };
  }

  const onSubmit = handleSubmit(async (values) => {
    if (fromEntry) {
      setBusy(true);
      try {
        const mutation = isCorrect ? correctMutation : editMutation;
        await mutation.mutateAsync(contenuFor(values));
        invalidateAfterEntry();
        queryClient.invalidateQueries({ queryKey: ['ecriture', associationId, entry!.id] });
        onSaved?.();
      } catch {
        // The edit/correct mutation's error state drives the Alert below.
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

  const error = isCorrect
    ? apiErrorMessage(correctMutation, 'Correction impossible.')
    : fromEntry
      ? apiErrorMessage(editMutation, 'Modification impossible.')
      : apiErrorMessage(activeMutation, 'Enregistrement impossible.');
  const loadError = categoriesQuery.isError || comptesQuery.isError;
  const quickAddSens: Sens = type === 'depense' ? 'depense' : 'recette';

  return {
    associationId,
    isCreate,
    isCorrect,
    fromEntry,
    isVirement,
    type,
    regimeTva,
    canEnter,
    canAddCategorie,
    canAddTiers,
    canAddEvenement,
    canAddJustificatif,
    register,
    errors,
    categories,
    comptes,
    tiersList,
    evenementsList,
    advancedOpen,
    setAdvancedOpen,
    catDialogOpen,
    setCatDialogOpen,
    tiersDialogOpen,
    setTiersDialogOpen,
    evenementDialogOpen,
    setEvenementDialogOpen,
    pendingFiles,
    onPickFiles,
    removePendingFile,
    fileInputRef,
    fileError,
    busy,
    success,
    error,
    loadError,
    quickAddSens,
    typeAllowed,
    selectType,
    onSubmit,
    onCategorieCreated,
    onTiersCreated,
    onEvenementCreated,
  };
}
