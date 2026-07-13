import { createContext, useContext } from 'react';

/**
 * How much accounting the interface shows (C3/C4).
 *
 * `simple` is the default and the promise: a volunteer sees "reçu / dépensé / sur
 * quel compte", never débit/crédit nor account numbers. `avance` reveals the
 * accountant's reading of the very same data — nothing is hidden, only folded.
 */
export type DisplayMode = 'simple' | 'avance';

export interface DisplayModeContextValue {
  mode: DisplayMode;
  /** True in `avance` — the phrasing most call sites read. */
  isAdvanced: boolean;
  setMode: (mode: DisplayMode) => void;
  toggle: () => void;
}

export const DisplayModeContext = createContext<DisplayModeContextValue | null>(null);

export function useDisplayMode(): DisplayModeContextValue {
  const ctx = useContext(DisplayModeContext);
  if (!ctx) throw new Error('useDisplayMode doit être utilisé dans un <DisplayModeProvider>.');
  return ctx;
}
