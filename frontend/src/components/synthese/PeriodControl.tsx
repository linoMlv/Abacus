import { cn } from '@/lib/utils';

import { type Preset, PRESET_LABELS } from './period';

export function PeriodControl({
  preset,
  onPreset,
  customFrom,
  customTo,
  onCustomFrom,
  onCustomTo,
}: {
  preset: Preset;
  onPreset: (p: Preset) => void;
  customFrom: string;
  customTo: string;
  onCustomFrom: (v: string) => void;
  onCustomTo: (v: string) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <div
        className="inline-flex rounded-lg border border-hairline bg-surface p-0.5"
        role="group"
        aria-label="Période"
      >
        {(Object.keys(PRESET_LABELS) as Preset[]).map((p) => (
          <button
            key={p}
            type="button"
            aria-pressed={preset === p}
            onClick={() => onPreset(p)}
            className={cn(
              'rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
              preset === p ? 'bg-accent text-white' : 'text-muted hover:text-ink'
            )}
          >
            {PRESET_LABELS[p]}
          </button>
        ))}
      </div>
      {preset === 'custom' && (
        <div className="flex items-center gap-1.5">
          <input
            type="date"
            aria-label="Date de début"
            value={customFrom}
            max={customTo || undefined}
            onChange={(e) => onCustomFrom(e.target.value)}
            className="h-9 rounded-lg border border-hairline bg-surface px-2 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
          />
          <span className="text-xs text-muted">au</span>
          <input
            type="date"
            aria-label="Date de fin"
            value={customTo}
            min={customFrom || undefined}
            onChange={(e) => onCustomTo(e.target.value)}
            className="h-9 rounded-lg border border-hairline bg-surface px-2 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
          />
        </div>
      )}
    </div>
  );
}
