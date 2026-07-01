import { Card } from '@/components/ui/card';

export function ChartsSkeleton() {
  return (
    <div className="space-y-4" aria-hidden>
      <Card className="h-64 animate-pulse bg-hover/50" />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="h-44 animate-pulse bg-hover/50" />
        <Card className="h-44 animate-pulse bg-hover/50" />
      </div>
    </div>
  );
}
