import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Check, Pencil, Trash2, Undo2, X } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';

import { accountingApi } from '@/api/accounting';
import { apiErrorMessage } from '@/api/client';
import { ManualEntryForm } from '@/components/saisie/ManualEntryForm';
import { OperationForm } from '@/components/saisie/OperationForm';
import { Alert } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { useDisplayMode } from '@/display/useDisplayMode';
import { usePermissions } from '@/hooks/usePermissions';
import { formatAmount, formatDate } from '@/lib/format';
import { PERMISSIONS } from '@/lib/permissions';

import { EcritureResume } from './EcritureResume';
import { JustificatifsSection } from './JustificatifsSection';
import { StatutBadge } from './StatutBadge';

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
  const { isAdvanced } = useDisplayMode();
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

              {isAdvanced ? (
                <table className="w-full text-sm">
                  <caption className="sr-only">Lignes de l’écriture en débit / crédit</caption>
                  <thead>
                    <tr className="border-b border-hairline text-left text-xs uppercase tracking-wider text-faint">
                      <th scope="col" className="py-2 font-medium">
                        Compte
                      </th>
                      <th scope="col" className="py-2 text-right font-medium">
                        Débit
                      </th>
                      <th scope="col" className="py-2 text-right font-medium">
                        Crédit
                      </th>
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
              ) : (
                <EcritureResume
                  associationId={associationId}
                  entry={entry}
                  comptes={comptesQuery.data ?? []}
                />
              )}

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
