import { Card } from '@/components/ui/card';
import { useDisplayMode } from '@/display/useDisplayMode';

import { JournalTableAccounting } from './JournalTableAccounting';
import { JournalTableSimple } from './JournalTableSimple';
import type { JournalTableProps } from './types';

/**
 * The journal, read at the level the user asked for (C24): plain language by
 * default, the accountant's columns when the advanced mode is on. Both render the
 * same rows from the same request — switching costs nothing.
 */
export function JournalTable(props: JournalTableProps) {
  const { isAdvanced } = useDisplayMode();
  return isAdvanced ? <JournalTableAccounting {...props} /> : <JournalTableSimple {...props} />;
}

/** Placeholder rows while the first page loads (avoids an empty-state flash). */
export function JournalSkeleton() {
  return (
    <Card className="overflow-hidden" aria-hidden>
      <div className="divide-y divide-hairline">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="flex items-center gap-4 px-4 py-3">
            <div className="h-3 w-20 animate-pulse rounded bg-hairline" />
            <div className="h-3 w-10 animate-pulse rounded bg-hairline" />
            <div className="h-3 flex-1 animate-pulse rounded bg-hairline" />
            <div className="h-3 w-16 animate-pulse rounded bg-hairline" />
          </div>
        ))}
      </div>
    </Card>
  );
}
