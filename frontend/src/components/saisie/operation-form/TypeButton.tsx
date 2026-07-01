import { cn } from '@/lib/utils';

export function TypeButton({
  active,
  tone,
  label,
  hint,
  disabled,
  onClick,
}: {
  active: boolean;
  tone: 'recette' | 'depense' | 'neutre';
  label: string;
  hint: string;
  disabled?: boolean;
  onClick: () => void;
}) {
  const activeRing = {
    recette: 'border-recette bg-recette-soft text-recette',
    depense: 'border-depense bg-depense-soft text-depense',
    neutre: 'border-accent bg-accent-soft text-accent',
  }[tone];
  return (
    <button
      type="button"
      aria-pressed={active}
      disabled={disabled}
      title={disabled ? 'Action non autorisée' : undefined}
      onClick={onClick}
      className={cn(
        'rounded-lg border px-4 py-3 text-left transition-colors',
        active ? activeRing : 'border-hairline bg-surface text-ink-soft hover:bg-hover',
        disabled && 'cursor-not-allowed opacity-50 hover:bg-surface'
      )}
    >
      <span className="block text-sm font-semibold">{label}</span>
      <span className="block text-xs opacity-80">{hint}</span>
    </button>
  );
}
