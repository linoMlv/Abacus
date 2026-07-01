import type { EcritureStatut } from '@/api/accounting';
import { Badge } from '@/components/ui/badge';

import { STATUT_LABELS } from './types';

export function StatutBadge({ statut }: { statut: EcritureStatut }) {
  return (
    <Badge variant={statut === 'validee' ? 'accent' : 'warning'}>{STATUT_LABELS[statut]}</Badge>
  );
}
