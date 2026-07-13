import { useDisplayMode } from './useDisplayMode';

/**
 * The one control over how much accounting the app shows (C3/C4).
 *
 * It lives in the topbar because the choice is the reader's, not the screen's: a
 * volunteer keeps "reçu / dépensé / sur quel compte" everywhere, an expert gets
 * débit/crédit and account numbers everywhere. Nothing is added or hidden from the
 * data — only from the reading.
 */
export function DisplayModeToggle() {
  const { isAdvanced, toggle } = useDisplayMode();

  return (
    <div className="flex items-center gap-2">
      <span className="hidden text-sm text-ink-soft sm:inline">Mode comptable</span>
      <button
        type="button"
        role="switch"
        aria-checked={isAdvanced}
        aria-label="Mode comptable (débit / crédit, numéros de comptes)"
        title="Affiche le détail comptable : débit / crédit, numéros de comptes"
        onClick={toggle}
        className={`relative h-5 w-9 shrink-0 rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 ${
          isAdvanced ? 'bg-accent' : 'bg-hairline'
        }`}
      >
        <span
          className={`absolute top-0.5 h-4 w-4 rounded-full bg-surface shadow-sm transition-transform ${
            isAdvanced ? 'translate-x-[1.125rem]' : 'translate-x-0.5'
          }`}
        />
      </button>
    </div>
  );
}
