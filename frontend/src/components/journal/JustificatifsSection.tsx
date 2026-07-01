import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Eye, Paperclip, Trash2 } from 'lucide-react';
import { useRef, useState } from 'react';

import {
  accountingApi,
  type Justificatif,
  JUSTIFICATIF_ACCEPT,
  JUSTIFICATIF_MAX_BYTES,
} from '@/api/accounting';
import { apiErrorMessage } from '@/api/client';
import { JustificatifViewer } from '@/components/JustificatifViewer';
import { Alert } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { usePermissions } from '@/hooks/usePermissions';
import { formatBytes } from '@/lib/format';
import { PERMISSIONS } from '@/lib/permissions';

/** Justificatifs of an entry: list, preview, upload (PDF/image, 5 Mo), delete. */
export function JustificatifsSection({
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
