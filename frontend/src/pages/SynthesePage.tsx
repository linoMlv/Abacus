import { ArrowRight } from 'lucide-react';
import { useNavigate, useParams } from 'react-router-dom';

import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { useActiveAssociation } from '@/hooks/useActiveAssociation';

function StatTile({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: string;
  hint: string;
  tone?: 'recette' | 'depense';
}) {
  const valueColor =
    tone === 'recette' ? 'text-recette' : tone === 'depense' ? 'text-depense' : 'text-ink';
  return (
    <Card className="p-5">
      <p className="text-xs font-medium uppercase tracking-wider text-faint">{label}</p>
      <p className={`tabular mt-3 text-2xl font-semibold ${valueColor}`}>{value}</p>
      <p className="mt-1 text-xs text-muted">{hint}</p>
    </Card>
  );
}

export function SynthesePage() {
  const { associationId } = useParams();
  const navigate = useNavigate();
  const association = useActiveAssociation();

  return (
    <div className="mx-auto max-w-6xl space-y-7">
      <div>
        <h2 className="text-xl font-semibold tracking-tight text-ink">
          {association?.name ?? 'Synthèse'}
        </h2>
        <p className="mt-1 text-sm text-muted">Vue d’ensemble de l’exercice en cours.</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile label="Trésorerie" value="—" hint="Solde consolidé des comptes" />
        <StatTile label="Résultat" value="—" hint="Exercice en cours" />
        <StatTile label="Recettes" value="—" hint="Cumul de l’exercice" tone="recette" />
        <StatTile label="Dépenses" value="—" hint="Cumul de l’exercice" tone="depense" />
      </div>

      <Card className="flex flex-col items-center gap-4 px-6 py-14 text-center">
        <div>
          <h3 className="text-base font-semibold text-ink">Aucune écriture pour l’instant</h3>
          <p className="mx-auto mt-1.5 max-w-sm text-sm text-muted">
            Enregistrez une première recette ou dépense : Abacus génère l’écriture comptable et met
            la synthèse à jour.
          </p>
        </div>
        <Button onClick={() => navigate(`/asso/${associationId}/saisie`)}>
          Saisir une opération
          <ArrowRight className="h-4 w-4" aria-hidden />
        </Button>
      </Card>
    </div>
  );
}
