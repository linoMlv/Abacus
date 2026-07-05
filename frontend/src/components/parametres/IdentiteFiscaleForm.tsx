import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { type FormEvent, useEffect, useState } from 'react';

import { associationApi, type AssociationSettings } from '@/api/members';
import { apiErrorMessage } from '@/api/client';
import { Alert } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

type FiscalFields = Omit<AssociationSettings, 'regime_tva'>;
const EMPTY: FiscalFields = {
  adresse: '',
  code_postal: '',
  ville: '',
  rna: '',
  siret: '',
  objet: '',
};

/**
 * Edit the association's fiscal identity — used to issue donation tax receipts.
 * The address and an RNA or SIRET are mandatory for a valid receipt (the receipt
 * endpoint refuses to issue one otherwise). SETTINGS_MANAGE.
 */
export function IdentiteFiscaleForm({ associationId }: { associationId: string }) {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ['association-settings', associationId],
    queryFn: () => associationApi.settings(associationId),
  });
  const [fields, setFields] = useState<FiscalFields>(EMPTY);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const s = query.data;
    if (!s) return;
    setFields({
      adresse: s.adresse ?? '',
      code_postal: s.code_postal ?? '',
      ville: s.ville ?? '',
      rna: s.rna ?? '',
      siret: s.siret ?? '',
      objet: s.objet ?? '',
    });
  }, [query.data]);

  const mutation = useMutation({
    mutationFn: () => associationApi.updateSettings(associationId, fields),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['association-settings', associationId] });
      setSaved(true);
    },
  });

  const set = (key: keyof FiscalFields) => (e: React.ChangeEvent<HTMLInputElement>) => {
    setSaved(false);
    setFields((f) => ({ ...f, [key]: e.target.value }));
  };

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    mutation.mutate();
  };

  const error = apiErrorMessage(mutation, 'Enregistrement impossible.');

  return (
    <Card className="p-5">
      <h3 className="text-sm font-semibold text-ink">Identité fiscale</h3>
      <p className="mt-1 text-sm text-muted">
        Adresse et identifiants de l’association, repris sur les reçus fiscaux de dons.
      </p>
      <form onSubmit={onSubmit} className="mt-4 space-y-4" noValidate>
        <div>
          <Label htmlFor="fisc-adresse">Adresse</Label>
          <Input
            id="fisc-adresse"
            className="mt-1.5"
            placeholder="N° et rue"
            value={fields.adresse ?? ''}
            onChange={set('adresse')}
          />
        </div>
        <div className="grid grid-cols-3 gap-3">
          <div>
            <Label htmlFor="fisc-cp">Code postal</Label>
            <Input
              id="fisc-cp"
              className="mt-1.5"
              value={fields.code_postal ?? ''}
              onChange={set('code_postal')}
            />
          </div>
          <div className="col-span-2">
            <Label htmlFor="fisc-ville">Ville</Label>
            <Input
              id="fisc-ville"
              className="mt-1.5"
              value={fields.ville ?? ''}
              onChange={set('ville')}
            />
          </div>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <Label htmlFor="fisc-rna">N° RNA</Label>
            <Input
              id="fisc-rna"
              className="mt-1.5"
              placeholder="W751234567"
              value={fields.rna ?? ''}
              onChange={set('rna')}
            />
          </div>
          <div>
            <Label htmlFor="fisc-siret">SIRET</Label>
            <Input
              id="fisc-siret"
              className="mt-1.5"
              value={fields.siret ?? ''}
              onChange={set('siret')}
            />
          </div>
        </div>
        <div>
          <Label htmlFor="fisc-objet">Objet</Label>
          <Input
            id="fisc-objet"
            className="mt-1.5"
            placeholder="Objet statutaire de l’association"
            value={fields.objet ?? ''}
            onChange={set('objet')}
          />
        </div>

        {error && <Alert>{error}</Alert>}

        <div className="flex items-center justify-end gap-3 pt-1">
          {saved && !mutation.isPending && (
            <span className="text-sm text-recette">Enregistré.</span>
          )}
          <Button type="submit" variant="accent" disabled={mutation.isPending || query.isLoading}>
            {mutation.isPending ? 'Enregistrement…' : 'Enregistrer'}
          </Button>
        </div>
      </form>
    </Card>
  );
}
