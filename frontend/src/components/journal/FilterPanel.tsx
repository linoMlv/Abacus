import { ChevronDown, X } from 'lucide-react';
import { type ReactNode, useState } from 'react';

import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';

import type { Facet } from './types';

export function ResetButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex items-center gap-1 text-xs font-medium text-muted hover:text-ink"
    >
      <X className="h-3.5 w-3.5" aria-hidden />
      Réinitialiser
    </button>
  );
}

function FilterGroup({
  title,
  count,
  children,
}: {
  title: string;
  count?: number;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  return (
    <section className="border-t border-hairline pt-4 first:border-0 first:pt-0">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((prev) => !prev)}
        className="flex w-full items-center gap-2 text-xs font-semibold uppercase tracking-wider text-faint transition-colors hover:text-muted"
      >
        <ChevronDown
          className={cn('h-3.5 w-3.5 shrink-0 transition-transform', !open && '-rotate-90')}
          aria-hidden
        />
        <span className="flex-1 text-left">{title}</span>
        {count ? (
          <span className="inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-accent-soft px-1 text-[10px] font-semibold normal-case text-accent">
            {count}
          </span>
        ) : null}
      </button>
      {open && <div className="mt-2">{children}</div>}
    </section>
  );
}

function FacetSection({ facet }: { facet: Facet }) {
  if (facet.options.length === 0) return null;
  return (
    <FilterGroup title={facet.title} count={facet.selected.length}>
      <ul className={cn('space-y-0.5', facet.scroll && 'max-h-44 overflow-y-auto')}>
        {facet.options.map((option) => (
          <li key={option.value}>
            <label className="flex cursor-pointer items-center gap-2.5 rounded-md px-1 py-1.5 text-sm text-ink hover:bg-hover">
              <input
                type="checkbox"
                className="h-4 w-4 shrink-0 rounded border-hairline accent-accent"
                checked={facet.selected.includes(option.value)}
                onChange={() => facet.onToggle(option.value)}
              />
              <span className="min-w-0 truncate">{option.label}</span>
            </label>
          </li>
        ))}
      </ul>
    </FilterGroup>
  );
}

export function FilterPanel({
  facets,
  dateFrom,
  dateTo,
  onDateFrom,
  onDateTo,
}: {
  facets: Facet[];
  dateFrom: string;
  dateTo: string;
  onDateFrom: (value: string) => void;
  onDateTo: (value: string) => void;
}) {
  return (
    <div className="space-y-4">
      <FilterGroup title="Période">
        <div className="space-y-2.5">
          <div>
            <label htmlFor="filtre-date-from" className="text-xs text-muted">
              Du
            </label>
            <Input
              id="filtre-date-from"
              type="date"
              aria-label="Date de début"
              className="mt-1"
              value={dateFrom}
              max={dateTo || undefined}
              onChange={(e) => onDateFrom(e.target.value)}
            />
          </div>
          <div>
            <label htmlFor="filtre-date-to" className="text-xs text-muted">
              Au
            </label>
            <Input
              id="filtre-date-to"
              type="date"
              aria-label="Date de fin"
              className="mt-1"
              value={dateTo}
              min={dateFrom || undefined}
              onChange={(e) => onDateTo(e.target.value)}
            />
          </div>
        </div>
      </FilterGroup>
      {facets.map((facet) => (
        <FacetSection key={facet.key} facet={facet} />
      ))}
    </div>
  );
}
