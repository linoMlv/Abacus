import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Check, Eye, Paperclip, Pencil, Trash2, Undo2, X } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';

import {
  accountingApi,
  type Justificatif,
  JUSTIFICATIF_ACCEPT,
  JUSTIFICATIF_MAX_BYTES,
} from '@/api/accounting';
import { apiErrorMessage } from '@/api/client';
import { JustificatifViewer } from '@/components/JustificatifViewer';
import { ManualEntryForm } from '@/components/saisie/ManualEntryForm';
import { OperationForm } from '@/components/saisie/OperationForm';
import { Alert } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { usePermissions } from '@/hooks/usePermissions';
import { formatAmount, formatBytes, formatDate } from '@/lib/format';
import { PERMISSIONS } from '@/lib/permissions';

import { StatutBadge } from './StatutBadge';

/** Justificatifs of an entry: list, preview, upload (PDF/image, 5 Mo), delete. */
function JustificatifsSection({
  associationId,
  ecritureId,
}: {
  associationId: string;
  ecritureId: string;
}) {
  const queryClient = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const [localError, setLocalError] = useState<string | null>(null);
  const [viewing, setViewing] = useState<Justificatif | null>(null);
  const { has } = usePermissions();
  const canManage = has(PERMISSIONS.ATTACHMENT_MANAGE);

  const listQuery = useQuery({
    queryKey: ['justificatifs', associationId, ecritureId],
    queryFn: () => accountingApi.listJustificatifs(associationId, ecritureId),
  });

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ['justificatifs', associationId, ecritureId] });

  const upload = useMutation({
    mutationFn: (file: File) => accountingApi.uploadJustificatif(associationId, ecritureId, file),
    onSuccess: invalidate,
  });
  const remove = useMutation({
    mutationFn: (id: string) => accountingApi.supprimerJustificatif(associationId, id),
    onSuccess: invalidate,
  });

  function onPick(e: React.ChangeEvent<HTMLInputElement>) {
    setLocalError(null);
    const file = e.target.files?.[0];
    e.target.value = ''; // allow re-picking the same file
    if (!file) return;
    // The server re-validates type and size — this is just a friendlier guard.
    if (file.size > JUSTIFICATIF_MAX_BYTES) {
      setLocalError('Fichier trop volumineux (5 Mo maximum).');
      return;
    }
    upload.mutate(file);
  }

  const items = listQuery.data ?? [];
  const error =
    localError ??
    apiErrorMessage(upload, 'Envoi du justificatif impossible.') ??
    apiErrorMessage(remove, 'Suppression impossible.');

  return (
    <section className="space-y-2 border-t border-hairline pt-4">
      <div className="flex items-center justify-between">
        <h4 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-faint">
          <Paperclip className="h-3.5 w-3.5" aria-hidden />
          Justificatifs
        </h4>
        {canManage && (
          <>
            <input
              ref={inputRef}
              type="file"
              accept={JUSTIFICATIF_ACCEPT}
              className="sr-only"
              onChange={onPick}
              aria-label="Ajouter un justificatif"
            />
            <Button
              variant="outline"
              size="sm"
              disabled={upload.isPending}
              onClick={() => inputRef.current?.click()}
            >
              {upload.isPending ? 'Envoi…' : 'Ajouter'}
            </Button>
          </>
        )}
      </div>

      {error && <Alert>{error}</Alert>}

      {items.length === 0 ? (
        <p className="text-xs text-muted">Aucun justificatif (PDF ou image, 5 Mo max).</p>
      ) : (
        <ul className="space-y-1.5">
          {items.map((j) => (
            <li
              key={j.id}
              className="flex items-center gap-2 rounded-lg border border-hairline px-3 py-2 text-sm"
            >
              <button
                type="button"
                onClick={() => setViewing(j)}
                className="flex min-w-0 flex-1 items-center gap-2 text-left"
                aria-label={`Aperçu de ${j.filename}`}
              >
                <Eye className="h-4 w-4 shrink-0 text-muted" aria-hidden />
                <span className="min-w-0 flex-1 truncate text-ink hover:text-accent">
                  {j.filename}
                </span>
              </button>
              <span className="shrink-0 text-xs text-faint">{formatBytes(j.size)}</span>
              {canManage && (
                <button
                  type="button"
                  onClick={() => remove.mutate(j.id)}
                  disabled={remove.isPending}
                  className="shrink-0 rounded-md p-1 text-faint hover:bg-hover hover:text-depense"
                  aria-label={`Supprimer ${j.filename}`}
                >
                  <Trash2 className="h-4 w-4" aria-hidden />
                </button>
              )}
            </li>
          ))}
        </ul>
      )}

      <JustificatifViewer
        associationId={associationId}
        justificatif={viewing}
        open={viewing !== null}
        onOpenChange={(o) => !o && setViewing(null)}
      />
    </section>
  );
}

export function EcritureDrawer({
  associationId,
  ecritureId,
  onClose,
}: {
  associationId: string;
  ecritureId: string;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const { has } = usePermissions();
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  // null = detail; 'edit' rebuilds a draft; 'correct' annule-et-remplace a validated entry.
  const [formAction, setFormAction] = useState<null | 'edit' | 'correct'>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) =>
      e.key === 'Escape' && (formAction ? setFormAction(null) : onClose());
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose, formAction]);

  const detailQuery = useQuery({
    queryKey: ['ecriture', associationId, ecritureId],
    queryFn: () => accountingApi.getEcriture(associationId, ecritureId),
  });
  const comptesQuery = useQuery({
    queryKey: ['comptes', associationId],
    queryFn: () => accountingApi.listComptes(associationId),
  });

  const compteLabel = useMemo(() => {
    const byId = new Map((comptesQuery.data ?? []).map((c) => [c.id, c]));
    return (id: string) => {
      const c = byId.get(id);
      return c ? `${c.numero} — ${c.libelle}` : id;
    };
  }, [comptesQuery.data]);

  const invalidateLists = () => {
    queryClient.invalidateQueries({ queryKey: ['ecritures', associationId] });
    queryClient.invalidateQueries({ queryKey: ['balance', associationId] });
    queryClient.invalidateQueries({ queryKey: ['synthese', associationId] });
  };

  const validate = useMutation({
    mutationFn: () => accountingApi.validerEcriture(associationId, ecritureId),
    onSuccess: () => {
      invalidateLists();
      queryClient.invalidateQueries({ queryKey: ['ecriture', associationId, ecritureId] });
    },
  });
  const remove = useMutation({
    mutationFn: () => accountingApi.supprimerEcriture(associationId, ecritureId),
    onSuccess: () => {
      invalidateLists();
      onClose();
    },
  });
  const contrepasser = useMutation({
    mutationFn: () => accountingApi.contrepasserEcriture(associationId, ecritureId),
    onSuccess: () => {
      invalidateLists();
      onClose();
    },
  });

  const entry = detailQuery.data;
  const isDraft = entry?.statut === 'brouillon';
  const canValidate = has(PERMISSIONS.ENTRY_VALIDATE);
  const canDelete = has(PERMISSIONS.ENTRY_DELETE);
  // The form-backed origines are editable in place; each needs its create permission.
  const formPermission =
    entry?.origine === 'virement'
      ? PERMISSIONS.ENTRY_CREATE_TRANSFER
      : entry?.origine === 'saisie_simple'
        ? PERMISSIONS.ENTRY_CREATE_SIMPLE
        : entry?.origine === 'manuelle'
          ? PERMISSIONS.ENTRY_CREATE_MANUAL
          : null;
  const isManuelle = entry?.origine === 'manuelle';
  const canUseForm = formPermission !== null && has(formPermission);
  const canEditEntry = isDraft && canUseForm; // Modifier (draft)
  // Corriger (validated): annule-et-remplace also needs the delete permission (reversal).
  const canCorrectEntry = entry !== undefined && !isDraft && canUseForm && canDelete;
  const formMode = formAction === 'correct' ? 'correct' : 'edit';

  function onFormSaved() {
    // A correction reverses the original and books the corrected draft elsewhere:
    // close the drawer. An edit stays, showing the refreshed entry.
    if (formAction === 'correct') {
      onClose();
    } else {
      setFormAction(null);
      queryClient.invalidateQueries({ queryKey: ['ecriture', associationId, ecritureId] });
    }
  }

  const actionError =
    apiErrorMessage(validate, 'Validation impossible.') ??
    apiErrorMessage(remove, 'Suppression impossible.') ??
    apiErrorMessage(contrepasser, 'Contre-passation impossible.');

  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      <button
        type="button"
        aria-label="Fermer"
        className="absolute inset-0 bg-ink/20"
        onClick={onClose}
      />
      <aside
        role="dialog"
        aria-modal="true"
        aria-label="Détail de l’écriture"
        className="relative flex h-full w-full max-w-md flex-col bg-surface shadow-xl"
      >
        <header className="flex items-center justify-between border-b border-hairline px-5 py-4">
          <h3 className="text-base font-semibold text-ink">
            {entry
              ? `${
                  formAction === 'correct'
                    ? 'Corriger la pièce'
                    : formAction === 'edit'
                      ? 'Modifier la pièce'
                      : 'Pièce'
                } n° ${entry.numero_piece}`
              : 'Détail'}
          </h3>
          <Button variant="ghost" size="icon" onClick={onClose} aria-label="Fermer">
            <X className="h-4 w-4" aria-hidden />
          </Button>
        </header>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          {detailQuery.isError && <Alert>Écriture introuvable.</Alert>}
          {entry && formAction && isManuelle && (
            <ManualEntryForm
              action={formAction}
              entry={entry}
              onSaved={onFormSaved}
              onCancel={() => setFormAction(null)}
            />
          )}
          {entry && formAction && !isManuelle && (
            <OperationForm
              mode={formMode}
              entry={entry}
              onSaved={onFormSaved}
              onCancel={() => setFormAction(null)}
            />
          )}
          {entry && !formAction && (
            <div className="space-y-4">
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted">{formatDate(entry.date)}</span>
                <StatutBadge statut={entry.statut} />
              </div>
              <p className="text-sm text-ink">{entry.libelle}</p>

              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-hairline text-left text-xs uppercase tracking-wider text-faint">
                    <th className="py-2 font-medium">Compte</th>
                    <th className="py-2 text-right font-medium">Débit</th>
                    <th className="py-2 text-right font-medium">Crédit</th>
                  </tr>
                </thead>
                <tbody>
                  {entry.lignes.map((l) => (
                    <tr key={l.id} className="border-b border-hairline last:border-0">
                      <td className="py-2 pr-2 text-ink">{compteLabel(l.compte_id)}</td>
                      <td className="py-2 text-right font-mono tabular-nums text-ink">
                        {Number(l.debit) > 0 ? formatAmount(l.debit) : ''}
                      </td>
                      <td className="py-2 text-right font-mono tabular-nums text-ink">
                        {Number(l.credit) > 0 ? formatAmount(l.credit) : ''}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <JustificatifsSection associationId={associationId} ecritureId={ecritureId} />
            </div>
          )}
        </div>

        {entry && !formAction && (
          <footer className="space-y-3 border-t border-hairline px-5 py-4">
            {actionError && <Alert>{actionError}</Alert>}
            {!isDraft ? (
              <div className="space-y-2.5">
                <p className="text-xs text-muted">
                  Écriture validée : immuable. « Corriger » crée la version corrigée et son extourne
                  en brouillon ; « Contre-passer » l’annule simplement.
                </p>
                <div className="flex flex-wrap gap-2">
                  {canCorrectEntry && (
                    <Button
                      variant="accent"
                      className="flex-1"
                      onClick={() => setFormAction('correct')}
                    >
                      <Pencil className="h-4 w-4" aria-hidden />
                      Corriger
                    </Button>
                  )}
                  {canDelete && (
                    <Button
                      variant="outline"
                      className="flex-1"
                      disabled={contrepasser.isPending}
                      onClick={() => contrepasser.mutate()}
                    >
                      <Undo2 className="h-4 w-4" aria-hidden />
                      Contre-passer
                    </Button>
                  )}
                </div>
              </div>
            ) : confirmingDelete ? (
              <div className="flex items-center gap-2">
                <span className="flex-1 text-sm text-ink">Supprimer ce brouillon ?</span>
                <Button variant="ghost" onClick={() => setConfirmingDelete(false)}>
                  Annuler
                </Button>
                <Button
                  variant="danger"
                  disabled={remove.isPending}
                  onClick={() => remove.mutate()}
                >
                  Confirmer
                </Button>
              </div>
            ) : (
              <div className="flex flex-wrap gap-2">
                {canValidate && (
                  <Button
                    variant="accent"
                    className="flex-1"
                    disabled={validate.isPending}
                    onClick={() => validate.mutate()}
                  >
                    <Check className="h-4 w-4" aria-hidden />
                    Valider
                  </Button>
                )}
                {canEditEntry && (
                  <Button variant="outline" onClick={() => setFormAction('edit')}>
                    <Pencil className="h-4 w-4" aria-hidden />
                    Modifier
                  </Button>
                )}
                {canDelete && (
                  <Button variant="outline" onClick={() => setConfirmingDelete(true)}>
                    <Trash2 className="h-4 w-4" aria-hidden />
                    Supprimer
                  </Button>
                )}
              </div>
            )}
          </footer>
        )}
      </aside>
    </div>
  );
}
