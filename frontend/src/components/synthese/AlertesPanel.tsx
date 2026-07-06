import { AlertTriangle, CalendarClock, FileClock, X } from 'lucide-react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import type { Synthese } from '@/api/accounting';
import { Card } from '@/components/ui/card';
import { formatDate, formatEUR } from '@/lib/format';
import { cn } from '@/lib/utils';

interface AlerteItem {
  /** Stable identity + volatile content: a dismissed alert re-surfaces if its content changes. */
  signature: string;
  icon: React.ReactNode;
  tone: 'accent' | 'warning' | 'depense';
  text: string;
  action?: string;
  onClick?: () => void;
}

/**
 * Per-association, client-side dismissal of synthesis alerts (localStorage-backed).
 * Keyed by a content signature so a hidden alert reappears when the situation
 * materially changes (more drafts, a new over-budget amount…). The server stays
 * the source of truth for the alerts themselves; this only hides acknowledged ones.
 */
function useDismissedAlerts(associationId: string) {
  const storageKey = `abacus.synthese.dismissedAlerts.${associationId}`;
  const [dismissed, setDismissed] = useState<string[]>(() => {
    try {
      const raw = localStorage.getItem(storageKey);
      return raw ? (JSON.parse(raw) as string[]) : [];
    } catch {
      return [];
    }
  });
  const dismiss = (signature: string) =>
    setDismissed((prev) => {
      if (prev.includes(signature)) return prev;
      const next = [...prev, signature];
      try {
        localStorage.setItem(storageKey, JSON.stringify(next));
      } catch {
        // Storage unavailable (private mode, quota): dismissal stays in-session.
      }
      return next;
    });
  return { isDismissed: (s: string) => dismissed.includes(s), dismiss };
}

function AlerteRow({ alerte, onDismiss }: { alerte: AlerteItem; onDismiss: () => void }) {
  const { icon, tone, text, action, onClick } = alerte;
  const toneColor =
    tone === 'depense' ? 'text-depense' : tone === 'warning' ? 'text-warning' : 'text-accent';
  return (
    <div className="flex items-center gap-3 px-4 py-3 text-sm">
      <span className={cn('shrink-0', toneColor)}>{icon}</span>
      <span className="min-w-0 flex-1 text-ink">{text}</span>
      {action && onClick && (
        <button
          type="button"
          onClick={onClick}
          className="shrink-0 text-xs font-medium text-accent hover:text-accent-hover"
        >
          {action}
        </button>
      )}
      <button
        type="button"
        onClick={onDismiss}
        aria-label="Masquer cette alerte"
        className="shrink-0 rounded-md p-1 text-faint transition-colors hover:bg-hover hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
      >
        <X className="h-3.5 w-3.5" aria-hidden />
      </button>
    </div>
  );
}

export function AlertesPanel({
  synthese,
  associationId,
}: {
  synthese: Synthese;
  associationId: string;
}) {
  const navigate = useNavigate();
  const { isDismissed, dismiss } = useDismissedAlerts(associationId);
  const { brouillons, evenements_depasses, exercices_a_cloturer, budgets_depasses } =
    synthese.alertes;

  const alertes: AlerteItem[] = [];
  if (brouillons > 0) {
    alertes.push({
      signature: `brouillons:${brouillons}`,
      icon: <FileClock className="h-4 w-4" aria-hidden />,
      tone: 'accent',
      text: `${brouillons} écriture${brouillons > 1 ? 's' : ''} en brouillon à valider`,
      action: 'Ouvrir le journal',
      onClick: () => navigate(`/asso/${associationId}/journal`),
    });
  }
  for (const ex of exercices_a_cloturer) {
    alertes.push({
      signature: `exercice:${ex.exercice_id}:${ex.date_fin}`,
      icon: <CalendarClock className="h-4 w-4" aria-hidden />,
      tone: 'warning',
      text: `Exercice « ${ex.libelle} » échu le ${formatDate(ex.date_fin)} — à clôturer`,
    });
  }
  for (const ev of evenements_depasses) {
    alertes.push({
      signature: `evenement:${ev.evenement_id}:${ev.realise_depenses}`,
      icon: <AlertTriangle className="h-4 w-4" aria-hidden />,
      tone: 'depense',
      text: `« ${ev.nom} » dépasse son budget (${formatEUR(ev.realise_depenses)} / ${formatEUR(ev.budget_depenses)})`,
      action: 'Voir les événements',
      onClick: () => navigate(`/asso/${associationId}/saisie?tab=evenements`),
    });
  }
  for (const b of budgets_depasses) {
    alertes.push({
      signature: `budget:${b.categorie_id}:${b.realise}`,
      icon: <AlertTriangle className="h-4 w-4" aria-hidden />,
      tone: 'depense',
      text: `« ${b.libelle} » dépasse son budget (${formatEUR(b.realise)} / ${formatEUR(b.montant_prevu)})`,
      action: 'Voir le budget',
      onClick: () => navigate(`/asso/${associationId}/budget`),
    });
  }

  const visible = alertes.filter((a) => !isDismissed(a.signature));
  if (visible.length === 0) return null;

  return (
    <Card className="divide-y divide-hairline p-0">
      {visible.map((a) => (
        <AlerteRow key={a.signature} alerte={a} onDismiss={() => dismiss(a.signature)} />
      ))}
    </Card>
  );
}
