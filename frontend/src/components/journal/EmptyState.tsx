import { useNavigate } from 'react-router-dom';

import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';

export function EmptyState({
  associationId,
  filtered,
}: {
  associationId: string;
  filtered: boolean;
}) {
  const navigate = useNavigate();
  return (
    <Card className="flex flex-col items-center gap-3 px-6 py-14 text-center">
      <h3 className="text-base font-semibold text-ink">
        {filtered ? 'Aucune écriture ne correspond' : 'Aucune écriture pour l’instant'}
      </h3>
      <p className="max-w-sm text-sm text-muted">
        {filtered
          ? 'Ajustez les filtres pour élargir la recherche.'
          : 'Enregistrez une première recette ou dépense ; elle apparaîtra ici.'}
      </p>
      {!filtered && (
        <Button variant="accent" onClick={() => navigate(`/asso/${associationId}/saisie`)}>
          Saisir une opération
        </Button>
      )}
    </Card>
  );
}
