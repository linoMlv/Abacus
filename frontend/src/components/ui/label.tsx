import { type LabelHTMLAttributes, forwardRef } from 'react';

import { cn } from '@/lib/utils';

export const Label = forwardRef<HTMLLabelElement, LabelHTMLAttributes<HTMLLabelElement>>(
  ({ className, ...props }, ref) => (
    <label ref={ref} className={cn('text-sm font-medium text-ink-soft', className)} {...props} />
  )
);
Label.displayName = 'Label';
