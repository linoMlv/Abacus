import { useDisplayMode } from '@/display/useDisplayMode';

/**
 * Reveals the accounting reading of the journal (débit/crédit, pièces, lignes).
 *
 * It flips the app-wide display mode rather than a local flag: someone who thinks
 * in débit/crédit wants that everywhere, and someone who does not should never
 * meet it. Both views show the same data — the switch changes the reading, never
 * what is counted.
 */
export function AdvancedSwitch() {
  const { isAdvanced, toggle } = useDisplayMode();

  return (
    <label className="flex cursor-pointer select-none items-center gap-2 text-sm text-ink-soft">
      <span className="hidden sm:inline">Vue comptable</span>
      <span className="sm:hidden">Avancé</span>
      <button
        type="button"
        role="switch"
        aria-checked={isAdvanced}
        aria-label="Vue comptable (débit / crédit)"
        onClick={toggle}
        className={`relative h-5 w-9 rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 ${
          isAdvanced ? 'bg-accent' : 'bg-hairline'
        }`}
      >
        <span
          className={`absolute top-0.5 h-4 w-4 rounded-full bg-surface shadow-sm transition-transform ${
            isAdvanced ? 'translate-x-[1.125rem]' : 'translate-x-0.5'
          }`}
        />
      </button>
    </label>
  );
}
