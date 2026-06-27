import { ChevronDown } from 'lucide-react';
import { type SelectHTMLAttributes, forwardRef } from 'react';

import { cn } from '@/lib/utils';

/**
 * Styled native <select>. Native is deliberate here: it is accessible and
 * keyboard-friendly out of the box, needs no dependency, and matches the sober
 * fintech look of {@link Input}. The chevron is decorative (the native control
 * draws its own on some platforms, so ours is purely visual).
 */
export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  ({ className, children, ...props }, ref) => (
    <div className="relative">
      <select
        ref={ref}
        className={cn(
          'h-10 w-full appearance-none rounded-lg border border-hairline bg-surface pl-3 pr-9 text-sm text-ink',
          'transition-colors focus-visible:outline-none focus-visible:border-accent focus-visible:ring-2 focus-visible:ring-accent/30',
          'disabled:cursor-not-allowed disabled:opacity-60',
          className
        )}
        {...props}
      >
        {children}
      </select>
      <ChevronDown
        className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-faint"
        aria-hidden
      />
    </div>
  )
);
Select.displayName = 'Select';
