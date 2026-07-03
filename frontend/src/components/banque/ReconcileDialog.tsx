import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { accountingApi, type LigneBancaire } from '@/api/accounting';
import { apiErrorMessage } from '@/api/client';
import { Alert } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import { formatDate, formatEUR } from '@/lib/format';

interface Props {
  associationId: string;
  ligne: LigneBancaire;
  open: boolean;
  onClose: () => void;
  onDone: () => void;
}

/** Reconcile a statement line: lettrer a suggested entry, or create the missing one. */
export function ReconcileDialog({ associationId, ligne, open, onClose, onDone }: Props) {
  const queryClient = useQueryClient();
  const montant = Number(ligne.montant);
  const sens = montant >= 0 ? 'recette' : 'depense';
  const [categorieId, setCategorieId] = useState('');

  const suggestionsQuery = useQuery({
    queryKey: ['banque', associationId, 'suggestions', ligne.id],
    queryFn: () => accountingApi.suggestionsRapprochement(associationId, ligne.id),
    enabled: open,
  });
  const categoriesQuery = useQuery({
    queryKey: ['categories', associationId, sens],
    queryFn: () => accountingApi.listCategories(associationId, sens),
    enabled: open,
  });

  function done() {
    queryClient.invalidateQueries({ queryKey: ['banque', associationId] });
    onDone();
    onClose();
  }

  const rapprocher = useMutation({
    mutationFn: (ecritureId: string) =>
      accountingApi.rapprocherLigne(associationId, ligne.id, ecritureId),
    onSuccess: done,
  });
  const creer = useMutation({
    mutationFn: () =>
      accountingApi.creerEcritureDepuisLigne(associationId, ligne.id, {
        categorie_id: categorieId,
      }),
    onSuccess: done,
  });

  const suggestions = suggestionsQuery.data ?? [];
  const categories = categoriesQuery.data ?? [];
  const error =
    apiErrorMessage(rapprocher, 'Rapprochement impossible.') ??
    apiErrorMessage(creer, 'Création impossible.');

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-lg">
        <DialogTitle>Rapprocher l’opération</DialogTitle>
        <DialogDescription>
          Associez cette ligne à une écriture existante, ou créez celle qui manque.
        </DialogDescription>

        <div className="mt-4 flex items-baseline justify-between rounded-lg border border-hairline bg-hover px-3.5 py-2.5">
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-ink">{ligne.libelle}</p>
            <p className="text-xs text-muted">{formatDate(ligne.date_operation)}</p>
          </div>
          <span
            className={`ml-3 shrink-0 font-mono text-sm font-semibold tabular-nums ${
              montant >= 0 ? 'text-recette' : 'text-depense'
            }`}
          >
            {formatEUR(ligne.montant)}
          </span>
        </div>

        {error && <Alert className="mt-4">{error}</Alert>}

        <section className="mt-5">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-faint">
            Écritures correspondantes
          </h4>
          {suggestionsQuery.isLoading ? (
            <p className="mt-2 text-sm text-muted">Recherche…</p>
          ) : suggestions.length === 0 ? (
            <p className="mt-2 text-sm text-muted">
              Aucune écriture du même montant trouvée à proximité de cette date.
            </p>
          ) : (
            <ul className="mt-2 space-y-1.5">
              {suggestions.map((s) => (
                <li
                  key={s.ecriture_id}
                  className="flex items-center gap-3 rounded-lg border border-hairline px-3 py-2"
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm text-ink">
                      <span className="text-faint">n°{s.numero_piece}</span> {s.libelle}
                    </p>
                    <p className="text-xs text-muted">{formatDate(s.date)}</p>
                  </div>
                  <span className="shrink-0 font-mono text-xs tabular-nums text-ink-soft">
                    {formatEUR(s.montant)}
                  </span>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={rapprocher.isPending}
                    onClick={() => rapprocher.mutate(s.ecriture_id)}
                  >
                    Lettrer
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="mt-5 border-t border-hairline pt-4">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-faint">
            Ou créer l’écriture ({sens === 'recette' ? 'recette' : 'dépense'})
          </h4>
          <div className="mt-2 space-y-2">
            <div>
              <Label htmlFor="reconcile-cat">Catégorie</Label>
              <Select
                id="reconcile-cat"
                value={categorieId}
                onChange={(e) => setCategorieId(e.target.value)}
                className="mt-1.5"
              >
                <option value="">Choisir une catégorie…</option>
                {categories
                  .filter((c) => c.is_active)
                  .map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.libelle}
                    </option>
                  ))}
              </Select>
            </div>
            <Button
              variant="accent"
              className="w-full"
              disabled={!categorieId || creer.isPending}
              onClick={() => creer.mutate()}
            >
              {creer.isPending ? 'Création…' : 'Créer et rapprocher'}
            </Button>
          </div>
        </section>
      </DialogContent>
    </Dialog>
  );
}
