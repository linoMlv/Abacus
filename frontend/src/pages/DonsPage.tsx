import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Download, HeartHandshake, Trash2 } from 'lucide-react';
import { useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';

import { type Don, donsApi } from '@/api/dons';
import { RecuDialog } from '@/components/dons/RecuDialog';
import { Alert } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { triggerDownload } from '@/lib/download';
import { formatDate, formatEUR } from '@/lib/format';

interface DonorGroup {
  tiers_id: string;
  tiers_nom: string;
  dons: Don[];
  total: number;
}

/** Group un-receipted dons by donor, so a receipt can be issued per donor. */
function groupByDonor(dons: Don[]): DonorGroup[] {
  const map = new Map<string, DonorGroup>();
  for (const don of dons) {
    const group = map.get(don.tiers_id) ?? {
      tiers_id: don.tiers_id,
      tiers_nom: don.tiers_nom,
      dons: [],
      total: 0,
    };
    group.dons.push(don);
    group.total += Number(don.montant);
    map.set(don.tiers_id, group);
  }
  return [...map.values()].sort((a, b) => a.tiers_nom.localeCompare(b.tiers_nom));
}

export function DonsPage() {
  const { associationId } = useParams() as { associationId: string };
  const queryClient = useQueryClient();
  const [dialogDonor, setDialogDonor] = useState<DonorGroup | null>(null);

  const donsQuery = useQuery({
    queryKey: ['dons', associationId, 'non_recu'],
    queryFn: () => donsApi.listDons(associationId, { non_recu: true }),
  });
  const recusQuery = useQuery({
    queryKey: ['recus', associationId],
    queryFn: () => donsApi.listRecus(associationId),
  });

  const deleteMutation = useMutation({
    mutationFn: (recuId: string) => donsApi.supprimerRecu(associationId, recuId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['recus', associationId] });
      queryClient.invalidateQueries({ queryKey: ['dons', associationId] });
    },
  });

  const groups = useMemo(() => groupByDonor(donsQuery.data ?? []), [donsQuery.data]);
  const recus = recusQuery.data ?? [];

  return (
    <div className="mx-auto max-w-4xl space-y-8">
      <div>
        <h2 className="text-xl font-semibold tracking-tight text-ink">Dons & reçus fiscaux</h2>
        <p className="mt-1 text-sm text-muted">
          Émettez les reçus Cerfa des dons reçus (par don ou cumul annuel par donateur).
        </p>
      </div>

      <section className="space-y-3">
        <h3 className="text-sm font-semibold text-ink-soft">Dons à recevoir un reçu</h3>
        {donsQuery.isError ? (
          <Alert>Impossible de charger les dons.</Alert>
        ) : groups.length === 0 ? (
          <Card className="p-6 text-center text-sm text-muted">
            Aucun don en attente de reçu. Un don est une recette validée rattachée à un donateur.
          </Card>
        ) : (
          <div className="space-y-3">
            {groups.map((group) => (
              <Card key={group.tiers_id} className="p-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <p className="font-medium text-ink">{group.tiers_nom}</p>
                    <p className="mt-0.5 text-sm text-muted">
                      {group.dons.length} don{group.dons.length > 1 ? 's' : ''} ·{' '}
                      <span className="tabular-nums">{formatEUR(group.total)}</span>
                    </p>
                  </div>
                  <Button variant="accent" onClick={() => setDialogDonor(group)}>
                    Établir un reçu
                  </Button>
                </div>
              </Card>
            ))}
          </div>
        )}
      </section>

      <section className="space-y-3">
        <h3 className="text-sm font-semibold text-ink-soft">Reçus émis</h3>
        {recusQuery.isError ? (
          <Alert>Impossible de charger les reçus.</Alert>
        ) : recus.length === 0 ? (
          <Card className="p-6 text-center text-sm text-muted">Aucun reçu émis.</Card>
        ) : (
          <Card className="divide-y divide-hairline p-0">
            {recus.map((recu) => (
              <div key={recu.id} className="flex items-center gap-3 px-4 py-3 text-sm">
                <HeartHandshake className="h-4 w-4 shrink-0 text-faint" aria-hidden />
                <div className="min-w-0 flex-1">
                  <p className="flex items-center gap-2 truncate font-medium text-ink">
                    <span className={recu.annule ? 'text-muted line-through' : undefined}>
                      Reçu n° {recu.numero} — {recu.tiers_nom}
                    </span>
                    {recu.annule && <Badge variant="neutral">Annulé</Badge>}
                  </p>
                  <p className="text-xs text-muted">
                    {formatDate(recu.date)} · année {recu.annee}
                  </p>
                </div>
                <span className="shrink-0 tabular-nums font-medium text-ink">
                  {formatEUR(recu.montant)}
                </span>
                {!recu.annule && (
                  <>
                    <button
                      type="button"
                      onClick={() => triggerDownload(donsApi.recuPdfUrl(associationId, recu.id))}
                      className="shrink-0 rounded-md p-1.5 text-faint hover:bg-hover hover:text-accent"
                      aria-label={`Télécharger le reçu n° ${recu.numero}`}
                    >
                      <Download className="h-4 w-4" aria-hidden />
                    </button>
                    <button
                      type="button"
                      onClick={() => deleteMutation.mutate(recu.id)}
                      disabled={deleteMutation.isPending}
                      className="shrink-0 rounded-md p-1.5 text-faint hover:bg-hover hover:text-depense"
                      aria-label={`Annuler le reçu n° ${recu.numero}`}
                    >
                      <Trash2 className="h-4 w-4" aria-hidden />
                    </button>
                  </>
                )}
              </div>
            ))}
          </Card>
        )}
      </section>

      {dialogDonor && (
        <RecuDialog
          associationId={associationId}
          donateur={{ id: dialogDonor.tiers_id, nom: dialogDonor.tiers_nom }}
          dons={dialogDonor.dons}
          open={!!dialogDonor}
          onOpenChange={(o) => !o && setDialogDonor(null)}
        />
      )}
    </div>
  );
}
