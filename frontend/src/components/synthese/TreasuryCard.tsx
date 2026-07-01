import { Pencil, Wallet } from 'lucide-react';

import { type CompteTresorerie, TYPE_TRESORERIE_LABELS } from '@/api/accounting';
import { Card } from '@/components/ui/card';
import { formatEUR } from '@/lib/format';

export function TreasuryCard({
  compte,
  onEdit,
}: {
  compte: CompteTresorerie;
  onEdit?: () => void;
}) {
  return (
    <Card className="flex items-center gap-4 p-4">
      <span
        className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg"
        style={{
          backgroundColor: compte.couleur ? `${compte.couleur}1a` : 'var(--color-accent-soft)',
          color: compte.couleur ?? 'var(--color-accent)',
        }}
        aria-hidden
      >
        <Wallet className="h-5 w-5" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-ink">{compte.libelle}</p>
        <p className="text-xs text-muted">{TYPE_TRESORERIE_LABELS[compte.type_tresorerie]}</p>
      </div>
      <p className="tabular shrink-0 text-base font-semibold text-ink">{formatEUR(compte.solde)}</p>
      {onEdit && (
        <button
          type="button"
          onClick={onEdit}
          aria-label={`Modifier ${compte.libelle}`}
          className="shrink-0 rounded-md p-1.5 text-faint transition-colors hover:bg-hover hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
        >
          <Pencil className="h-4 w-4" />
        </button>
      )}
    </Card>
  );
}
