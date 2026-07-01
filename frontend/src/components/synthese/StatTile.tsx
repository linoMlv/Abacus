import { Card } from '@/components/ui/card';

export function StatTile({
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
