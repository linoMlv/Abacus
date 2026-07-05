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

/**
 * Create or edit a third party (name + type, plus an optional postal address).
 * The address is what a donor's tax receipt needs, so it is offered here even
 * though most tiers don't require it.
 */
export function TiersDialog({
  associationId,
  tiers,
  defaultType = 'fournisseur',
  open,
  onOpenChange,
  onSaved,
}: {
  associationId: string;
  tiers?: Tiers | null;
  defaultType?: TypeTiers;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved?: (tiers: Tiers) => void;
}) {
  const isEdit = !!tiers;
  const queryClient = useQueryClient();
  const [nom, setNom] = useState('');
  const [type, setType] = useState<TypeTiers>(defaultType);
  const [adresse, setAdresse] = useState('');
  const [codePostal, setCodePostal] = useState('');
  const [ville, setVille] = useState('');

  useEffect(() => {
    if (!open) return;
    setNom(tiers?.nom ?? '');
    setType(tiers?.type ?? defaultType);
    setAdresse(tiers?.adresse ?? '');
    setCodePostal(tiers?.code_postal ?? '');
    setVille(tiers?.ville ?? '');
  }, [open, tiers, defaultType]);

  const mutation = useMutation({
    mutationFn: () => {
      const payload = {
        nom: nom.trim(),
        type,
        adresse: adresse.trim() || null,
        code_postal: codePostal.trim() || null,
        ville: ville.trim() || null,
      };
      return isEdit
        ? accountingApi.modifierTiers(associationId, tiers.id, payload)
        : accountingApi.creerTiers(associationId, payload);
    },
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
        <DialogTitle>{isEdit ? 'Modifier le tiers' : 'Nouveau tiers'}</DialogTitle>
        <DialogDescription>
          Fournisseur, adhérent, donateur ou financeur. L’adresse est requise sur un reçu fiscal de
          don.
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
          <div>
            <Label htmlFor="tiers-adresse">Adresse</Label>
            <Input
              id="tiers-adresse"
              className="mt-1.5"
              placeholder="N° et rue"
              value={adresse}
              onChange={(e) => setAdresse(e.target.value)}
            />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <Label htmlFor="tiers-cp">Code postal</Label>
              <Input
                id="tiers-cp"
                className="mt-1.5"
                value={codePostal}
                onChange={(e) => setCodePostal(e.target.value)}
              />
            </div>
            <div className="col-span-2">
              <Label htmlFor="tiers-ville">Ville</Label>
              <Input
                id="tiers-ville"
                className="mt-1.5"
                value={ville}
                onChange={(e) => setVille(e.target.value)}
              />
            </div>
          </div>

          {error && <Alert>{error}</Alert>}

          <div className="flex justify-end pt-1">
            <Button type="submit" variant="accent" disabled={mutation.isPending}>
              {mutation.isPending ? 'Enregistrement…' : isEdit ? 'Enregistrer' : 'Créer'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
