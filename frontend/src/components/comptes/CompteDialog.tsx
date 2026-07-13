import { useMutation, useQueryClient } from '@tanstack/react-query';
import { type FormEvent, useEffect, useState } from 'react';

import {
  accountingApi,
  CLASSES,
  COMPTE_TYPE_LABELS,
  type Compte,
  type CompteType,
  typesForClasse,
} from '@/api/accounting';
import { apiErrorMessage } from '@/api/client';
import { Alert } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';

/**
 * Guided creation / rename of an account (C10).
 *
 * Guided path: the user picks the rubrique the account belongs under and the
 * server proposes the next free number (606 → 6061). The number only surfaces
 * for whoever asks for it ("choisir le numéro moi-même"), and the nature is
 * pre-decided whenever the classe pins it (6 → charge, 7 → produit).
 *
 * On rename the number is not editable at all: entries, the balance and the FEC
 * reference it, so renumbering would rewrite history.
 */
export function CompteDialog({
  associationId,
  compte,
  classe: initialClasse,
  rubriques,
  open,
  onOpenChange,
}: {
  associationId: string;
  /** Account being renamed, or null/undefined to create one. */
  compte?: Compte | null;
  /** Classe pre-selected when creating (the section the user clicked from). */
  classe?: number;
  /** Existing accounts, used to offer the rubriques of the selected classe. */
  rubriques: Compte[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const isEdit = !!compte;
  const queryClient = useQueryClient();

  const [classe, setClasse] = useState(initialClasse ?? 6);
  const [prefixe, setPrefixe] = useState('');
  const [libelle, setLibelle] = useState('');
  const [type, setType] = useState<CompteType>('charge');
  const [customNumero, setCustomNumero] = useState(false);
  const [numero, setNumero] = useState('');

  const natures = typesForClasse(classe);
  const rubriquesDeLaClasse = rubriques
    .filter((c) => c.classe === classe && c.numero.length <= 3)
    .sort((a, b) => a.numero.localeCompare(b.numero));

  useEffect(() => {
    if (!open) return;
    const startClasse = compte?.classe ?? initialClasse ?? 6;
    setClasse(startClasse);
    setLibelle(compte?.libelle ?? '');
    setType(compte?.type ?? typesForClasse(startClasse)[0]);
    setPrefixe('');
    setCustomNumero(false);
    setNumero('');
  }, [open, compte, initialClasse]);

  /** Changing the family invalidates the rubrique, and pins the nature it implies. */
  function selectClasse(next: number) {
    setClasse(next);
    setPrefixe('');
    setType((current) =>
      typesForClasse(next).includes(current) ? current : typesForClasse(next)[0]
    );
  }

  const mutation = useMutation({
    mutationFn: () => {
      const nom = libelle.trim();
      if (isEdit) {
        return accountingApi.modifierCompte(associationId, compte.id, { libelle: nom });
      }
      return accountingApi.creerCompte(associationId, {
        libelle: nom,
        type,
        ...(customNumero ? { numero: numero.trim() } : { prefixe }),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['plan-comptable', associationId] });
      onOpenChange(false);
    },
  });

  const canSubmit =
    libelle.trim().length > 0 && (isEdit || (customNumero ? numero.trim().length > 1 : !!prefixe));

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    mutation.mutate();
  };

  const error = apiErrorMessage(mutation, 'Enregistrement impossible.');

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogTitle>{isEdit ? 'Renommer le compte' : 'Nouveau compte'}</DialogTitle>
        <DialogDescription>
          {isEdit
            ? `Le numéro ${compte.numero} ne change pas : vos écritures s’y réfèrent.`
            : 'Choisissez la rubrique : le numéro est attribué automatiquement.'}
        </DialogDescription>

        <form onSubmit={onSubmit} className="mt-5 space-y-4" noValidate>
          {!isEdit && (
            <div>
              <Label htmlFor="compte-classe">Famille</Label>
              <Select
                id="compte-classe"
                className="mt-1.5"
                value={String(classe)}
                onChange={(e) => selectClasse(Number(e.target.value))}
              >
                {CLASSES.map((c) => (
                  <option key={c.classe} value={c.classe}>
                    {c.label} — {c.hint}
                  </option>
                ))}
              </Select>
            </div>
          )}

          {!isEdit && !customNumero && (
            <div>
              <Label htmlFor="compte-rubrique">Rubrique</Label>
              <Select
                id="compte-rubrique"
                className="mt-1.5"
                value={prefixe}
                onChange={(e) => setPrefixe(e.target.value)}
              >
                <option value="">Choisir une rubrique…</option>
                {rubriquesDeLaClasse.map((c) => (
                  <option key={c.id} value={c.numero}>
                    {c.numero} — {c.libelle}
                  </option>
                ))}
              </Select>
              <p className="mt-1.5 text-xs text-muted">
                Le nouveau compte prendra le premier numéro libre sous cette rubrique.
              </p>
            </div>
          )}

          {!isEdit && customNumero && (
            <div>
              <Label htmlFor="compte-numero">Numéro</Label>
              <Input
                id="compte-numero"
                className="mt-1.5 font-mono"
                inputMode="numeric"
                placeholder="6135"
                value={numero}
                onChange={(e) => setNumero(e.target.value)}
              />
              <p className="mt-1.5 text-xs text-muted">
                Commence par la classe ({classe}) et compte au moins deux chiffres.
              </p>
            </div>
          )}

          <div>
            <Label htmlFor="compte-libelle">Libellé</Label>
            <Input
              id="compte-libelle"
              className="mt-1.5"
              placeholder="Location de salle"
              value={libelle}
              onChange={(e) => setLibelle(e.target.value)}
              autoFocus
            />
          </div>

          {!isEdit && natures.length > 1 && (
            <div>
              <Label htmlFor="compte-type">Nature</Label>
              <Select
                id="compte-type"
                className="mt-1.5"
                value={type}
                onChange={(e) => setType(e.target.value as CompteType)}
              >
                {natures.map((n) => (
                  <option key={n} value={n}>
                    {COMPTE_TYPE_LABELS[n]}
                  </option>
                ))}
              </Select>
            </div>
          )}

          {!isEdit && (
            <button
              type="button"
              onClick={() => setCustomNumero((v) => !v)}
              className="text-xs font-medium text-accent underline-offset-2 hover:underline"
            >
              {customNumero ? 'Revenir au numéro automatique' : 'Choisir le numéro moi-même'}
            </button>
          )}

          {error && <Alert>{error}</Alert>}

          <div className="flex justify-end pt-1">
            <Button type="submit" variant="accent" disabled={!canSubmit || mutation.isPending}>
              {mutation.isPending ? 'Enregistrement…' : isEdit ? 'Enregistrer' : 'Créer le compte'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
