import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import {
  accountingApi,
  type CreateRecurrenceInput,
  PERIODICITE_LABELS,
  type Periodicite,
  type Recurrence,
  RECURRENCE_MODE_LABELS,
  type RecurrenceMode,
} from '@/api/accounting';
import { apiErrorMessage } from '@/api/client';
import { Alert } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';

interface Props {
  associationId: string;
  recurrence?: Recurrence;
  open: boolean;
  onClose: () => void;
}

const PERIODICITES = Object.keys(PERIODICITE_LABELS) as Periodicite[];
const MODES = Object.keys(RECURRENCE_MODE_LABELS) as RecurrenceMode[];

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

/** Create or edit a recurring entry template + its schedule. */
export function RecurrenceDialog({ associationId, recurrence, open, onClose }: Props) {
  const queryClient = useQueryClient();
  const isEdit = !!recurrence;
  const [libelle, setLibelle] = useState(recurrence?.libelle ?? '');
  const [categorieId, setCategorieId] = useState(recurrence?.categorie_id ?? '');
  const [compteId, setCompteId] = useState(recurrence?.compte_tresorerie_id ?? '');
  const [montant, setMontant] = useState(recurrence?.montant ?? '');
  const [periodicite, setPeriodicite] = useState<Periodicite>(
    recurrence?.periodicite ?? 'mensuelle'
  );
  const [prochaine, setProchaine] = useState(recurrence?.prochaine_echeance ?? today());
  const [dateFin, setDateFin] = useState(recurrence?.date_fin ?? '');
  const [mode, setMode] = useState<RecurrenceMode>(recurrence?.mode ?? 'proposition');
  const [localError, setLocalError] = useState<string | null>(null);

  const categoriesQuery = useQuery({
    queryKey: ['categories', associationId, 'all'],
    queryFn: () => accountingApi.listCategories(associationId),
    enabled: open,
  });
  const comptesQuery = useQuery({
    queryKey: ['tresorerie', associationId],
    queryFn: () => accountingApi.listTresorerie(associationId),
    enabled: open,
  });

  const mutation = useMutation({
    mutationFn: () => {
      const base: CreateRecurrenceInput = {
        libelle,
        categorie_id: categorieId,
        compte_tresorerie_id: compteId,
        montant,
        periodicite,
        prochaine_echeance: prochaine,
        mode,
      };
      if (isEdit) {
        // Send date_fin explicitly (null when cleared) so an existing end date
        // can be removed; a create just omits it when empty.
        return accountingApi.modifierRecurrence(associationId, recurrence.id, {
          ...base,
          date_fin: dateFin || null,
        });
      }
      return accountingApi.creerRecurrence(
        associationId,
        dateFin ? { ...base, date_fin: dateFin } : base
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['recurrences', associationId] });
      onClose();
    },
  });

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLocalError(null);
    if (!categorieId || !compteId) {
      setLocalError('Choisissez une catégorie et un compte.');
      return;
    }
    if (!(Number(montant) > 0)) {
      setLocalError('Le montant doit être strictement positif.');
      return;
    }
    mutation.mutate();
  }

  const categories = (categoriesQuery.data ?? []).filter((c) => c.is_active);
  const comptes = (comptesQuery.data ?? []).filter((c) => c.is_active);
  const error = localError ?? apiErrorMessage(mutation, 'Enregistrement impossible.');

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-lg">
        <DialogTitle>{isEdit ? 'Modifier la récurrence' : 'Nouvelle récurrence'}</DialogTitle>
        <DialogDescription>
          Une opération répétée (loyer, abonnement, cotisation…) générée à chaque échéance.
        </DialogDescription>

        <form onSubmit={onSubmit} className="mt-4 space-y-4">
          <div>
            <Label htmlFor="rec-libelle">Libellé</Label>
            <Input
              id="rec-libelle"
              value={libelle}
              onChange={(e) => setLibelle(e.target.value)}
              placeholder="Loyer du local"
              className="mt-1.5"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="rec-cat">Catégorie</Label>
              <Select
                id="rec-cat"
                value={categorieId}
                onChange={(e) => setCategorieId(e.target.value)}
                className="mt-1.5"
              >
                <option value="">Choisir…</option>
                {categories.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.libelle} ({c.sens === 'recette' ? 'recette' : 'dépense'})
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <Label htmlFor="rec-compte">Compte</Label>
              <Select
                id="rec-compte"
                value={compteId}
                onChange={(e) => setCompteId(e.target.value)}
                className="mt-1.5"
              >
                <option value="">Choisir…</option>
                {comptes.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.libelle}
                  </option>
                ))}
              </Select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="rec-montant">Montant (€)</Label>
              <Input
                id="rec-montant"
                type="number"
                min="0"
                step="0.01"
                value={montant}
                onChange={(e) => setMontant(e.target.value)}
                className="mt-1.5"
              />
            </div>
            <div>
              <Label htmlFor="rec-periodicite">Périodicité</Label>
              <Select
                id="rec-periodicite"
                value={periodicite}
                onChange={(e) => setPeriodicite(e.target.value as Periodicite)}
                className="mt-1.5"
              >
                {PERIODICITES.map((p) => (
                  <option key={p} value={p}>
                    {PERIODICITE_LABELS[p]}
                  </option>
                ))}
              </Select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="rec-prochaine">Prochaine échéance</Label>
              <Input
                id="rec-prochaine"
                type="date"
                value={prochaine}
                onChange={(e) => setProchaine(e.target.value)}
                className="mt-1.5"
              />
            </div>
            <div>
              <Label htmlFor="rec-fin">Fin (facultatif)</Label>
              <Input
                id="rec-fin"
                type="date"
                value={dateFin}
                onChange={(e) => setDateFin(e.target.value)}
                className="mt-1.5"
              />
            </div>
          </div>

          <div>
            <Label htmlFor="rec-mode">Mode</Label>
            <Select
              id="rec-mode"
              value={mode}
              onChange={(e) => setMode(e.target.value as RecurrenceMode)}
              className="mt-1.5"
            >
              {MODES.map((m) => (
                <option key={m} value={m}>
                  {RECURRENCE_MODE_LABELS[m]}
                </option>
              ))}
            </Select>
            <p className="mt-1 text-xs text-faint">
              {mode === 'auto'
                ? "L'écriture est créée et validée automatiquement à l'échéance."
                : "À l'échéance, un brouillon est proposé ; vous le validez."}
            </p>
          </div>

          {error && <Alert>{error}</Alert>}

          <div className="flex gap-2">
            <Button type="button" variant="ghost" className="flex-1" onClick={onClose}>
              Annuler
            </Button>
            <Button type="submit" variant="accent" className="flex-1" disabled={mutation.isPending}>
              {mutation.isPending ? 'Enregistrement…' : isEdit ? 'Enregistrer' : 'Créer'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
