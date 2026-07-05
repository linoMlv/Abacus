import { useMutation, useQueryClient } from '@tanstack/react-query';
import { type FormEvent, useEffect, useMemo, useState } from 'react';

import { type Don, donsApi, FORME_DON_LABELS, type FormeDon } from '@/api/dons';
import { apiErrorMessage } from '@/api/client';
import { Alert } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import { formatDate, formatEUR } from '@/lib/format';

const FORMES = Object.keys(FORME_DON_LABELS) as FormeDon[];

/** Issue a receipt for a donor: pick the dons to include, form, date and year. */
export function RecuDialog({
  associationId,
  donateur,
  dons,
  open,
  onOpenChange,
}: {
  associationId: string;
  donateur: { id: string; nom: string };
  dons: Don[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [forme, setForme] = useState<FormeDon>('numeraire');
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [annee, setAnnee] = useState(() => new Date().getFullYear());

  useEffect(() => {
    if (!open) return;
    setSelected(new Set(dons.map((d) => d.ecriture_id)));
    setForme('numeraire');
    setDate(new Date().toISOString().slice(0, 10));
    // Default the fiscal year to the most recent don's year, else this year.
    const years = dons.map((d) => Number(d.date.slice(0, 4)));
    setAnnee(years.length ? Math.max(...years) : new Date().getFullYear());
  }, [open, dons]);

  const total = useMemo(
    () =>
      dons.filter((d) => selected.has(d.ecriture_id)).reduce((s, d) => s + Number(d.montant), 0),
    [dons, selected]
  );

  const mutation = useMutation({
    mutationFn: () =>
      donsApi.creerRecu(associationId, {
        tiers_id: donateur.id,
        ecriture_ids: [...selected],
        date,
        annee,
        forme,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dons', associationId] });
      queryClient.invalidateQueries({ queryKey: ['recus', associationId] });
      onOpenChange(false);
    },
  });

  const toggle = (id: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (selected.size === 0) return;
    mutation.mutate();
  };

  const error = apiErrorMessage(mutation, 'Émission impossible.');

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogTitle>Établir un reçu fiscal</DialogTitle>
        <DialogDescription>
          Donateur : <span className="font-medium text-ink">{donateur.nom}</span>. Sélectionnez les
          dons à inclure (un reçu unique par don ou cumulatif annuel).
        </DialogDescription>

        <form onSubmit={onSubmit} className="mt-5 space-y-4" noValidate>
          <div className="max-h-52 space-y-1.5 overflow-y-auto rounded-lg border border-hairline p-2">
            {dons.map((d) => (
              <label
                key={d.ecriture_id}
                className="flex cursor-pointer items-center gap-3 rounded-md px-2 py-1.5 text-sm hover:bg-hover"
              >
                <input
                  type="checkbox"
                  className="h-4 w-4 accent-accent"
                  checked={selected.has(d.ecriture_id)}
                  onChange={() => toggle(d.ecriture_id)}
                />
                <span className="w-24 shrink-0 text-muted tabular-nums">{formatDate(d.date)}</span>
                <span className="min-w-0 flex-1 truncate text-ink">{d.libelle}</span>
                <span className="shrink-0 tabular-nums text-ink">{formatEUR(d.montant)}</span>
              </label>
            ))}
          </div>

          <div className="flex items-center justify-between rounded-lg bg-hover px-3 py-2 text-sm font-semibold">
            <span className="text-ink">Total du reçu</span>
            <span className="tabular-nums text-ink">{formatEUR(total)}</span>
          </div>

          <div className="grid gap-3 sm:grid-cols-3">
            <div>
              <Label htmlFor="recu-forme">Forme du don</Label>
              <Select
                id="recu-forme"
                className="mt-1.5"
                value={forme}
                onChange={(e) => setForme(e.target.value as FormeDon)}
              >
                {FORMES.map((f) => (
                  <option key={f} value={f}>
                    {FORME_DON_LABELS[f]}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <Label htmlFor="recu-annee">Année</Label>
              <Input
                id="recu-annee"
                type="number"
                className="mt-1.5"
                value={annee}
                onChange={(e) => setAnnee(Number(e.target.value))}
              />
            </div>
            <div>
              <Label htmlFor="recu-date">Date du reçu</Label>
              <Input
                id="recu-date"
                type="date"
                className="mt-1.5"
                value={date}
                onChange={(e) => setDate(e.target.value)}
              />
            </div>
          </div>

          {error && <Alert>{error}</Alert>}

          <div className="flex justify-end pt-1">
            <Button
              type="submit"
              variant="accent"
              disabled={mutation.isPending || selected.size === 0}
            >
              {mutation.isPending ? 'Émission…' : 'Établir le reçu'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
