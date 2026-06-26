import type { HTMLAttributes } from 'react';

import { cn } from '@/lib/utils';

/** Inline error/notice block, announced to assistive tech via role="alert". */
export function Alert({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      role="alert"
      className={cn(
        'rounded-lg border border-depense/20 bg-depense-soft px-3.5 py-2.5 text-sm text-depense',
        className
      )}
      {...props}
    />
  );
}
