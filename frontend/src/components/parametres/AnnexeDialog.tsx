import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowDown, ArrowUp, Download, FileText, Plus, Trash2 } from 'lucide-react';
import { useEffect, useState } from 'react';

import { accountingApi, type AnnexeRubrique, type Exercice } from '@/api/accounting';
import { apiErrorMessage } from '@/api/client';
import { Alert } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';

/** Edit an exercice's narrative annexe: its ANC rubrics (title + free text). */
export function AnnexeDialog({
  associationId,
  exercice,
  onOpenChange,
}: {
  associationId: string;
  exercice: Exercice | null;
  onOpenChange: (open: boolean) => void;
}) {
  const open = exercice !== null;
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        {exercice && <AnnexeEditor associationId={associationId} exercice={exercice} />}
      </DialogContent>
    </Dialog>
  );
}

function AnnexeEditor({ associationId, exercice }: { associationId: string; exercice: Exercice }) {
  const queryClient = useQueryClient();
  const key = ['annexe', associationId, exercice.id];
  const invalidate = () => queryClient.invalidateQueries({ queryKey: key });

  const query = useQuery({
    queryKey: key,
    queryFn: () => accountingApi.listAnnexe(associationId, exercice.id),
  });
  const rubriques = query.data ?? [];

  const add = useMutation({
    mutationFn: () =>
      accountingApi.ajouterRubrique(associationId, exercice.id, {
        titre: 'Nouvelle rubrique',
      }),
    onSuccess: invalidate,
  });
  const reorder = useMutation({
    mutationFn: (ids: string[]) => accountingApi.reordonnerAnnexe(associationId, exercice.id, ids),
    onSuccess: invalidate,
  });

  const move = (index: number, delta: number) => {
    const next = [...rubriques];
    const target = index + delta;
    if (target < 0 || target >= next.length) return;
    [next[index], next[target]] = [next[target], next[index]];
    reorder.mutate(next.map((r) => r.id));
  };

  return (
    <>
      <DialogTitle>Annexe — {exercice.libelle}</DialogTitle>
      <DialogDescription className="flex flex-wrap items-center justify-between gap-2">
        <span>
          Commentaires narratifs des comptes annuels (règles comptables, faits marquants,
          engagements…). Ils s’ajoutent aux tableaux calculés dans le PDF.
        </span>
        <a
          href={accountingApi.annexePdfUrl(associationId, { date_to: exercice.date_fin })}
          target="_blank"
          rel="noreferrer"
          className="inline-flex shrink-0 items-center gap-1.5 text-sm font-medium text-accent hover:underline"
        >
          <Download className="h-4 w-4" aria-hidden /> PDF
        </a>
      </DialogDescription>

      <div className="mt-4 max-h-[60vh] space-y-3 overflow-y-auto pr-1">
        {query.isError ? (
          <Alert>Impossible de charger l’annexe.</Alert>
        ) : query.isLoading ? (
          <p className="py-6 text-center text-sm text-muted">Chargement…</p>
        ) : rubriques.length === 0 ? (
          <p className="flex items-center gap-2 py-6 text-sm text-muted">
            <FileText className="h-4 w-4" aria-hidden /> Aucune rubrique.
          </p>
        ) : (
          rubriques.map((rubrique, index) => (
            <RubriqueCard
              key={rubrique.id}
              associationId={associationId}
              rubrique={rubrique}
              onChanged={invalidate}
              onMoveUp={index > 0 ? () => move(index, -1) : undefined}
              onMoveDown={index < rubriques.length - 1 ? () => move(index, 1) : undefined}
            />
          ))
        )}
      </div>

      {add.isError && <Alert className="mt-3">{apiErrorMessage(add, 'Ajout impossible.')}</Alert>}
      <div className="mt-4 border-t border-hairline pt-4">
        <Button variant="outline" size="sm" onClick={() => add.mutate()} disabled={add.isPending}>
          <Plus className="h-4 w-4" aria-hidden /> Ajouter une rubrique
        </Button>
      </div>
    </>
  );
}

function RubriqueCard({
  associationId,
  rubrique,
  onChanged,
  onMoveUp,
  onMoveDown,
}: {
  associationId: string;
  rubrique: AnnexeRubrique;
  onChanged: () => void;
  onMoveUp?: () => void;
  onMoveDown?: () => void;
}) {
  const [titre, setTitre] = useState(rubrique.titre);
  const [contenu, setContenu] = useState(rubrique.contenu);

  // Keep local drafts in sync when the server copy changes (e.g. after reorder).
  useEffect(() => {
    setTitre(rubrique.titre);
    setContenu(rubrique.contenu);
  }, [rubrique.titre, rubrique.contenu]);

  const save = useMutation({
    mutationFn: () =>
      accountingApi.modifierRubrique(associationId, rubrique.id, {
        titre: titre.trim(),
        contenu,
      }),
    onSuccess: onChanged,
  });
  const remove = useMutation({
    mutationFn: () => accountingApi.supprimerRubrique(associationId, rubrique.id),
    onSuccess: onChanged,
  });

  const dirty = titre.trim() !== rubrique.titre || contenu !== rubrique.contenu;
  const canSave = dirty && titre.trim().length > 0;

  return (
    <div className="rounded-lg border border-hairline bg-surface p-3.5">
      <div className="flex items-center gap-2">
        <Input
          value={titre}
          onChange={(e) => setTitre(e.target.value)}
          aria-label="Titre de la rubrique"
          className="font-medium"
        />
        <div className="flex shrink-0 items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            onClick={onMoveUp}
            disabled={!onMoveUp}
            aria-label="Monter"
          >
            <ArrowUp className="h-4 w-4" aria-hidden />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={onMoveDown}
            disabled={!onMoveDown}
            aria-label="Descendre"
          >
            <ArrowDown className="h-4 w-4" aria-hidden />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => remove.mutate()}
            disabled={remove.isPending}
            aria-label="Supprimer la rubrique"
          >
            <Trash2 className="h-4 w-4 text-depense" aria-hidden />
          </Button>
        </div>
      </div>
      <Textarea
        value={contenu}
        onChange={(e) => setContenu(e.target.value)}
        aria-label="Contenu de la rubrique"
        placeholder="Rédigez le texte de cette rubrique…"
        className="mt-2"
        rows={4}
      />
      {(save.isError || remove.isError) && (
        <Alert className="mt-2">
          {apiErrorMessage(save.isError ? save : remove, 'Enregistrement impossible.')}
        </Alert>
      )}
      <div className="mt-2 flex justify-end">
        <Button size="sm" onClick={() => save.mutate()} disabled={!canSave || save.isPending}>
          {save.isPending ? 'Enregistrement…' : 'Enregistrer'}
        </Button>
      </div>
    </div>
  );
}
