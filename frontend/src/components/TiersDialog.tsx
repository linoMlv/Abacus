import { useMutation, useQueryClient } from '@tanstack/react-query';
import { type FormEvent, useEffect, useState } from 'react';

import { accountingApi, type Tiers, type TypeTiers, TYPE_TIERS_LABELS } from '@/api/accounting';
import { apiErrorMessage } from '@/api/client';
import { Alert } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';

const TYPES = Object.keys(TYPE_TIERS_LABELS) as TypeTiers[];

/** Quick-add a third party (a name + a type) without leaving the saisie screen. */
export function TiersDialog({
  associationId,
  defaultType = 'fournisseur',
  open,
  onOpenChange,
  onSaved,
}: {
  associationId: string;
  defaultType?: TypeTiers;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved?: (tiers: Tiers) => void;
}) {
  const queryClient = useQueryClient();
  const [nom, setNom] = useState('');
  const [type, setType] = useState<TypeTiers>(defaultType);

  useEffect(() => {
    if (!open) return;
    setNom('');
    setType(defaultType);
  }, [open, defaultType]);

  const mutation = useMutation({
    mutationFn: () => accountingApi.creerTiers(associationId, { nom: nom.trim(), type }),
    onSuccess: (saved) => {
      queryClient.invalidateQueries({ queryKey: ['tiers', associationId] });
      onSaved?.(saved);
      onOpenChange(false);
    },
  });

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!nom.trim()) return;
    mutation.mutate();
  };

  const error = apiErrorMessage(mutation, 'Enregistrement impossible.');

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogTitle>Nouveau tiers</DialogTitle>
        <DialogDescription>
          Fournisseur, adhérent, donateur ou financeur lié à l’opération.
        </DialogDescription>

        <form onSubmit={onSubmit} className="mt-5 space-y-4" noValidate>
          <div>
            <Label htmlFor="tiers-nom">Nom</Label>
            <Input
              id="tiers-nom"
              className="mt-1.5"
              placeholder="Mairie, Imprimeur, M. Dupont…"
              value={nom}
              onChange={(e) => setNom(e.target.value)}
              autoFocus
            />
          </div>
          <div>
            <Label htmlFor="tiers-type">Type</Label>
            <Select
              id="tiers-type"
              className="mt-1.5"
              value={type}
              onChange={(e) => setType(e.target.value as TypeTiers)}
            >
              {TYPES.map((t) => (
                <option key={t} value={t}>
                  {TYPE_TIERS_LABELS[t]}
                </option>
              ))}
            </Select>
          </div>

          {error && <Alert>{error}</Alert>}

          <div className="flex justify-end pt-1">
            <Button type="submit" variant="accent" disabled={mutation.isPending}>
              {mutation.isPending ? 'Enregistrement…' : 'Créer'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
