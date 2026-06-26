import { Loader2 } from 'lucide-react';

export function FullScreenLoader({ label = 'Chargement…' }: { label?: string }) {
  return (
    <div className="flex min-h-dvh items-center justify-center bg-canvas">
      <div className="flex items-center gap-3 text-muted">
        <Loader2 className="h-5 w-5 animate-spin" aria-hidden />
        <span className="text-sm">{label}</span>
      </div>
    </div>
  );
}
