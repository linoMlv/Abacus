import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Lock, Plus } from 'lucide-react';
import { useState } from 'react';

import { accountingApi, EXERCICE_STATUT_LABELS, type Exercice } from '@/api/accounting';
import { apiErrorMessage } from '@/api/client';
import { Alert } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { formatDate } from '@/lib/format';
import { ClotureDialog } from './ClotureDialog';

/** Manage fiscal years: list them, open a new one, close the current one. */
export function ExercicesPanel({ associationId }: { associationId: string }) {
  const queryClient = useQueryClient();
  const exercicesQuery = useQuery({
    queryKey: ['exercices', associationId],
    queryFn: () => accountingApi.listExercices(associationId),
  });
  const exercices = exercicesQuery.data ?? [];

  const [creating, setCreating] = useState(false);
  const [closing, setClosing] = useState<Exercice | null>(null);

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted">
          Un exercice comptable couvre une période (souvent l’année civile). Le clôturer détermine
          le résultat, génère le report à nouveau et verrouille les écritures.
        </p>
        <Button size="sm" onClick={() => setCreating(true)}>
          <Plus className="h-4 w-4" aria-hidden /> Nouvel exercice
        </Button>
      </div>

      {exercicesQuery.isError ? (
        <Alert>Impossible de charger les exercices.</Alert>
      ) : exercices.length === 0 ? (
        <Card className="p-4 text-sm text-muted">Aucun exercice.</Card>
      ) : (
        <ul className="space-y-2">
          {exercices.map((exercice) => (
            <li key={exercice.id}>
              <Card className="flex flex-wrap items-center justify-between gap-3 p-3.5">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-ink">{exercice.libelle}</span>
                    <Badge variant={exercice.statut === 'ouvert' ? 'accent' : 'neutral'}>
                      {EXERCICE_STATUT_LABELS[exercice.statut]}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted">
                    du {formatDate(exercice.date_debut)} au {formatDate(exercice.date_fin)}
                  </p>
                </div>
                {exercice.statut === 'ouvert' ? (
                  <Button size="sm" variant="outline" onClick={() => setClosing(exercice)}>
                    <Lock className="h-4 w-4" aria-hidden /> Clôturer
                  </Button>
                ) : (
                  <span className="text-xs text-faint">Verrouillé</span>
                )}
              </Card>
            </li>
          ))}
        </ul>
      )}

      <CreateExerciceDialog
        associationId={associationId}
        open={creating}
        onOpenChange={setCreating}
        onCreated={() => queryClient.invalidateQueries({ queryKey: ['exercices', associationId] })}
      />
      <ClotureDialog
        associationId={associationId}
        exercice={closing}
        onOpenChange={(open) => !open && setClosing(null)}
      />
    </div>
  );
}

function CreateExerciceDialog({
  associationId,
  open,
  onOpenChange,
  onCreated,
}: {
  associationId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: () => void;
}) {
  const [libelle, setLibelle] = useState('');
  const [dateDebut, setDateDebut] = useState('');
  const [dateFin, setDateFin] = useState('');

  const create = useMutation({
    mutationFn: () =>
      accountingApi.creerExercice(associationId, {
        libelle: libelle.trim(),
        date_debut: dateDebut,
        date_fin: dateFin,
      }),
    onSuccess: () => {
      onCreated();
      onOpenChange(false);
      setLibelle('');
      setDateDebut('');
      setDateFin('');
    },
  });

  const valid = libelle.trim() && dateDebut && dateFin && dateFin > dateDebut;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogTitle>Nouvel exercice</DialogTitle>
        <DialogDescription>
          Ouvrez une nouvelle période comptable (dates paramétrables, exercices décalés possibles).
          Elle ne doit pas chevaucher un exercice existant.
        </DialogDescription>
        <form
          className="mt-4 space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (valid) create.mutate();
          }}
        >
          <div>
            <Label htmlFor="ex-libelle">Libellé</Label>
            <Input
              id="ex-libelle"
              value={libelle}
              onChange={(e) => setLibelle(e.target.value)}
              placeholder="Ex. 2027"
              autoFocus
              required
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="ex-debut">Début</Label>
              <Input
                id="ex-debut"
                type="date"
                value={dateDebut}
                max={dateFin || undefined}
                onChange={(e) => setDateDebut(e.target.value)}
                required
              />
            </div>
            <div>
              <Label htmlFor="ex-fin">Fin</Label>
              <Input
                id="ex-fin"
                type="date"
                value={dateFin}
                min={dateDebut || undefined}
                onChange={(e) => setDateFin(e.target.value)}
                required
              />
            </div>
          </div>
          {create.isError && <Alert>{apiErrorMessage(create, 'Création impossible.')}</Alert>}
          <div className="flex justify-end gap-2 border-t border-hairline pt-4">
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
              Annuler
            </Button>
            <Button type="submit" disabled={create.isPending || !valid}>
              {create.isPending ? 'Création…' : 'Créer'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
