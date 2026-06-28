import { Download } from 'lucide-react';

import { accountingApi, type Justificatif } from '@/api/accounting';
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog';
import { formatBytes } from '@/lib/format';

/**
 * In-app preview of a justificatif: images in an <img>, PDFs in a sandboxed
 * <iframe> (the server serves the preview inline with `nosniff` + CSP `sandbox`,
 * and only ever for strictly type-validated PDF/images). A download button
 * remains for anything else, or to save the file.
 */
export function JustificatifViewer({
  associationId,
  justificatif,
  open,
  onOpenChange,
}: {
  associationId: string;
  justificatif: Justificatif | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const apercuUrl = justificatif
    ? accountingApi.justificatifApercuUrl(associationId, justificatif.id)
    : '';
  const downloadUrl = justificatif
    ? accountingApi.justificatifContenuUrl(associationId, justificatif.id)
    : '';
  const isImage = justificatif?.content_type.startsWith('image/') ?? false;
  const isPdf = justificatif?.content_type === 'application/pdf';

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[90vh] w-[92vw] max-w-3xl flex-col gap-3 p-4">
        <div className="flex items-center justify-between gap-3 pr-8">
          <DialogTitle className="min-w-0 truncate text-base">
            {justificatif?.filename ?? 'Justificatif'}
          </DialogTitle>
          {justificatif && (
            <a
              href={downloadUrl}
              className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-hairline px-3 py-1.5 text-sm font-medium text-ink-soft hover:bg-hover"
            >
              <Download className="h-4 w-4" aria-hidden />
              Télécharger
            </a>
          )}
        </div>

        <div className="min-h-0 flex-1 overflow-auto rounded-lg border border-hairline bg-canvas">
          {justificatif && isImage && (
            <img
              src={apercuUrl}
              alt={justificatif.filename}
              className="mx-auto max-h-[75vh] w-auto object-contain"
            />
          )}
          {justificatif && isPdf && (
            <iframe src={apercuUrl} title={justificatif.filename} className="h-[75vh] w-full" />
          )}
          {justificatif && !isImage && !isPdf && (
            <p className="p-6 text-center text-sm text-muted">
              Aperçu indisponible pour ce format ({formatBytes(justificatif.size)}). Utilisez «
              Télécharger ».
            </p>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
