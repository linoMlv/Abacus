import { useQuery } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';

import { accountingApi, EXERCICE_STATUT_LABELS } from '@/api/accounting';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';

/** Fiscal-year picker shared by the balance and the ledger ("" = tous). */
export function ExerciceSelect({
  id,
  value,
  onChange,
}: {
  id: string;
  value: string;
  onChange: (exerciceId: string) => void;
}) {
  const { associationId } = useParams() as { associationId: string };
  const query = useQuery({
    queryKey: ['exercices', associationId],
    queryFn: () => accountingApi.listExercices(associationId),
  });
  const exercices = query.data ?? [];

  return (
    <div className="min-w-52">
      <Label htmlFor={id}>Exercice</Label>
      <Select
        id={id}
        className="mt-1.5"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={query.isLoading}
      >
        <option value="">Tous les exercices</option>
        {exercices.map((ex) => (
          <option key={ex.id} value={ex.id}>
            {ex.libelle} ({EXERCICE_STATUT_LABELS[ex.statut].toLowerCase()})
          </option>
        ))}
      </Select>
    </div>
  );
}
