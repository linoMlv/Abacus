import { CheckCircle2, Plus } from 'lucide-react';
import { Link } from 'react-router-dom';

import { type Ecriture } from '@/api/accounting';
import { CategorieDialog } from '@/components/CategorieDialog';
import { EvenementDialog } from '@/components/EvenementDialog';
import { TiersDialog } from '@/components/TiersDialog';
import { Alert } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';

import { AdvancedFields } from './operation-form/AdvancedFields';
import { CompteOptions, FieldError } from './operation-form/fields';
import { TypeButton } from './operation-form/TypeButton';
import { type OperationMode, useOperationForm } from './operation-form/useOperationForm';

export interface OperationFormProps {
  /**
   * - ``create``: the Saisie tab (a new entry).
   * - ``edit``: rebuild an existing *draft* in place (PATCH).
   * - ``correct``: correct a *validated* entry — books a reversal plus the
   *   corrected draft in one call (annule-et-remplace), the original untouched.
   */
  mode: OperationMode;
  /** The entry being edited or corrected (required outside create mode). */
  entry?: Ecriture;
  /** Called after a successful edit/correction (e.g. to close the drawer). */
  onSaved?: () => void;
  /** Called when the user cancels. */
  onCancel?: () => void;
}

/**
 * The type-first operation form, shared by creation (Saisie tab), the inline
 * edition of a draft and the correction of a validated entry (journal drawer).
 * Outside create mode the type is locked to the entry's origine (a saisie_simple
 * stays recette/dépense, a virement stays a virement — changing origine is not an
 * edit) and the fields are pre-filled from the entry; submitting issues a ``PATCH``
 * (edit) or a contre-passation with replacement (correct) instead of a new entry.
 */
export function OperationForm({ mode, entry, onSaved, onCancel }: OperationFormProps) {
  const f = useOperationForm({ mode, entry, onSaved });
  const {
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
    register,
    errors,
    categories,
    comptes,
    tiersList,
    evenementsList,
    busy,
    success,
    error,
    loadError,
    quickAddSens,
    typeAllowed,
    selectType,
    onSubmit,
  } = f;

  if (!canEnter) {
    return (
      <Card className="p-6 text-sm text-muted">
        Vous n’avez pas l’autorisation de saisir des opérations.
      </Card>
    );
  }

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
                  onClick={() => f.setCatDialogOpen(true)}
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
        <AdvancedFields
          register={register}
          errors={errors}
          isVirement={isVirement}
          isCreate={isCreate}
          fromEntry={fromEntry}
          regimeTva={regimeTva}
          advancedOpen={f.advancedOpen}
          setAdvancedOpen={f.setAdvancedOpen}
          canAddTiers={canAddTiers}
          canAddEvenement={canAddEvenement}
          canAddJustificatif={f.canAddJustificatif}
          tiersList={tiersList}
          evenementsList={evenementsList}
          onOpenTiersDialog={() => f.setTiersDialogOpen(true)}
          onOpenEvenementDialog={() => f.setEvenementDialogOpen(true)}
          pendingFiles={f.pendingFiles}
          onPickFiles={f.onPickFiles}
          removePendingFile={f.removePendingFile}
          fileInputRef={f.fileInputRef}
          fileError={f.fileError}
        />

        {isCorrect && (
          <p className="text-xs text-muted">
            La correction contre-passe l’écriture validée et crée la version corrigée en brouillon
            (l’originale reste inchangée), à valider ensuite.
          </p>
        )}

        {error && <Alert>{error}</Alert>}
        {isCreate && success && (
          <div
            role="status"
            className="flex items-center gap-2 rounded-lg border border-recette/20 bg-recette-soft px-3.5 py-2.5 text-sm text-recette"
          >
            <CheckCircle2 className="h-4 w-4" aria-hidden />
            {success}
          </div>
        )}

        {fromEntry ? (
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
          open={f.catDialogOpen}
          onOpenChange={f.setCatDialogOpen}
          onSaved={f.onCategorieCreated}
        />
      )}
      {canAddTiers && (
        <TiersDialog
          associationId={associationId}
          defaultType={type === 'recette' ? 'donateur' : 'fournisseur'}
          open={f.tiersDialogOpen}
          onOpenChange={f.setTiersDialogOpen}
          onSaved={f.onTiersCreated}
        />
      )}
      {canAddEvenement && (
        <EvenementDialog
          associationId={associationId}
          evenement={null}
          open={f.evenementDialogOpen}
          onOpenChange={f.setEvenementDialogOpen}
          onSaved={f.onEvenementCreated}
        />
      )}
    </>
  );

  if (fromEntry) {
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
