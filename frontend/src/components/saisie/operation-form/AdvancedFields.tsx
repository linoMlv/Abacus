import { ChevronDown, Paperclip, Plus, X } from 'lucide-react';
import type { RefObject } from 'react';
import type { FieldErrors, UseFormRegister } from 'react-hook-form';

import {
  type Evenement,
  JUSTIFICATIF_ACCEPT,
  MODE_REGLEMENT_LABELS,
  type Tiers,
} from '@/api/accounting';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import { formatBytes } from '@/lib/format';
import { cn } from '@/lib/utils';
import { MODE_REGLEMENT_VALUES, type SaisieForm } from '@/pages/saisie.schema';

import { FieldError } from './fields';

interface AdvancedFieldsProps {
  register: UseFormRegister<SaisieForm>;
  errors: FieldErrors<SaisieForm>;
  isVirement: boolean;
  isCreate: boolean;
  fromEntry: boolean;
  advancedOpen: boolean;
  setAdvancedOpen: (updater: (v: boolean) => boolean) => void;
  canAddTiers: boolean;
  canAddEvenement: boolean;
  canAddJustificatif: boolean;
  tiersList: Tiers[];
  evenementsList: Evenement[];
  onOpenTiersDialog: () => void;
  onOpenEvenementDialog: () => void;
  pendingFiles: File[];
  onPickFiles: (e: React.ChangeEvent<HTMLInputElement>) => void;
  removePendingFile: (index: number) => void;
  fileInputRef: RefObject<HTMLInputElement | null>;
  fileError: string | null;
}

/** The collapsible "Avancé" block: tiers, event, libellé, payment, reference, files. */
export function AdvancedFields({
  register,
  errors,
  isVirement,
  isCreate,
  fromEntry,
  advancedOpen,
  setAdvancedOpen,
  canAddTiers,
  canAddEvenement,
  canAddJustificatif,
  tiersList,
  evenementsList,
  onOpenTiersDialog,
  onOpenEvenementDialog,
  pendingFiles,
  onPickFiles,
  removePendingFile,
  fileInputRef,
  fileError,
}: AdvancedFieldsProps) {
  return (
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
                    onClick={onOpenTiersDialog}
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
                    onClick={onOpenEvenementDialog}
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

          {isCreate && canAddJustificatif && (
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
                      <span className="shrink-0 text-xs text-faint">{formatBytes(file.size)}</span>
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
          {fromEntry && (
            <p className="text-xs text-faint">
              Les justificatifs se gèrent depuis le détail de l’écriture.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
