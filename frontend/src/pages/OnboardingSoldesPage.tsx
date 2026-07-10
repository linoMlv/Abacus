import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, Wallet } from 'lucide-react';
import { useState } from 'react';
import { Navigate, useNavigate, useParams } from 'react-router-dom';

import { accountingApi, type CompteTresorerie, TYPE_TRESORERIE_LABELS } from '@/api/accounting';
import { apiErrorMessage } from '@/api/client';
import { BrandWordmark } from '@/components/Brand';
import { TreasuryAccountDialog } from '@/components/TreasuryAccountDialog';
import { Alert } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { useActiveAssociation } from '@/hooks/useActiveAssociation';
import { today } from '@/lib/format';
import { amountToDecimalString } from '@/pages/saisie.schema';

const AMOUNT_PATTERN = /^-?\d+([.,]\d{1,2})?$/;

/**
 * Onboarding step right after creating an association: declare the starting
 * balance of each treasury account (the seeded Banque/Caisse, plus any added).
 * Fully skippable and editable later from the Synthèse.
 */
export function OnboardingSoldesPage() {
  const { associationId } = useParams() as { associationId: string };
  const association = useActiveAssociation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [amounts, setAmounts] = useState<Record<string, string>>({});
  const [dialogOpen, setDialogOpen] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  const tresorerieQuery = useQuery({
    queryKey: ['tresorerie', associationId],
    queryFn: () => accountingApi.listTresorerie(associationId),
  });
  const comptes = tresorerieQuery.data ?? [];

  const goToSynthese = () => navigate(`/asso/${associationId}/synthese`, { replace: true });

  const save = useMutation({
    mutationFn: async (entries: Array<[string, string]>) => {
      for (const [compteId, raw] of entries) {
        await accountingApi.definirSoldeInitial(associationId, compteId, {
          montant: amountToDecimalString(raw),
          date_solde_initial: today(),
        });
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tresorerie', associationId] });
      goToSynthese();
    },
  });

  function onFinish() {
    setLocalError(null);
    const filled = Object.entries(amounts)
      .map(([id, v]) => [id, v.trim()] as [string, string])
      .filter(([, v]) => v !== '');
    if (filled.some(([, v]) => !AMOUNT_PATTERN.test(v))) {
      setLocalError('Un montant est invalide (ex. 1500,00).');
      return;
    }
    if (filled.length === 0) {
      goToSynthese();
      return;
    }
    save.mutate(filled);
  }

  // Membership is the authorization (re-checked server-side on every request);
  // the URL pointing at an association the user left simply sends them home.
  if (!association) return <Navigate to="/" replace />;

  const error = localError ?? apiErrorMessage(save, 'Enregistrement impossible.');

  return (
    <div className="flex min-h-dvh flex-col bg-canvas">
      <header className="flex h-16 items-center px-6 lg:px-8">
        <BrandWordmark />
      </header>
      <div className="flex flex-1 justify-center px-6 pb-16">
        <div className="w-full max-w-lg">
          <h1 className="text-xl font-semibold tracking-tight text-ink">Vos soldes de départ</h1>
          <p className="mt-1.5 text-sm text-muted">
            Indiquez le solde actuel de chaque compte pour démarrer la comptabilité au bon montant.
            Vous pourrez le modifier ou en ajouter plus tard.
          </p>

          <div className="mt-6 space-y-3">
            {comptes.map((compte) => (
              <SoldeRow
                key={compte.id}
                compte={compte}
                value={amounts[compte.id] ?? ''}
                onChange={(v) => setAmounts((prev) => ({ ...prev, [compte.id]: v }))}
              />
            ))}
          </div>

          <Button variant="outline" size="sm" className="mt-4" onClick={() => setDialogOpen(true)}>
            <Plus className="h-4 w-4" aria-hidden />
            Ajouter un compte
          </Button>

          {error && <Alert className="mt-5">{error}</Alert>}

          <div className="mt-7 flex items-center justify-between gap-3">
            <Button variant="ghost" onClick={goToSynthese} disabled={save.isPending}>
              Passer
            </Button>
            <Button variant="accent" onClick={onFinish} disabled={save.isPending}>
              {save.isPending ? 'Enregistrement…' : 'Enregistrer et continuer'}
            </Button>
          </div>
        </div>
      </div>

      <TreasuryAccountDialog
        associationId={associationId}
        open={dialogOpen}
        onOpenChange={setDialogOpen}
      />
    </div>
  );
}

function SoldeRow({
  compte,
  value,
  onChange,
}: {
  compte: CompteTresorerie;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <Card className="flex items-center gap-4 p-4">
      <span
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-accent-soft text-accent"
        aria-hidden
      >
        <Wallet className="h-4 w-4" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-ink">{compte.libelle}</p>
        <p className="text-xs text-muted">{TYPE_TRESORERIE_LABELS[compte.type_tresorerie]}</p>
      </div>
      <Input
        aria-label={`Solde de ${compte.libelle}`}
        inputMode="decimal"
        placeholder="0,00"
        className="w-32 text-right font-mono tabular-nums"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </Card>
  );
}
