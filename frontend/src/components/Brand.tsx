import { cn } from '@/lib/utils';

/** Compact abacus mark: three rails of beads, one accented. */
export function BrandMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={cn('h-7 w-7', className)} role="img" aria-label="Abacus">
      <rect x="3" y="3" width="26" height="26" rx="7" className="fill-ink" />
      <g stroke="#94a3b8" strokeWidth="1.1">
        <line x1="8" y1="11" x2="24" y2="11" />
        <line x1="8" y1="16" x2="24" y2="16" />
        <line x1="8" y1="21" x2="24" y2="21" />
      </g>
      <g className="fill-white">
        <circle cx="12" cy="11" r="2.1" />
        <circle cx="19" cy="11" r="2.1" />
        <circle cx="11" cy="16" r="2.1" />
        <circle cx="20" cy="21" r="2.1" />
      </g>
      <circle cx="16" cy="16" r="2.1" className="fill-accent" />
      <circle cx="13" cy="21" r="2.1" className="fill-accent" />
    </svg>
  );
}

export function BrandWordmark({ className }: { className?: string }) {
  return (
    <div className={cn('flex items-center gap-2.5', className)}>
      <BrandMark />
      <span className="text-[17px] font-semibold tracking-tight text-ink">Abacus</span>
    </div>
  );
}
