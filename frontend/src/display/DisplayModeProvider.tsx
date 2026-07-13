import { type ReactNode, useCallback, useMemo, useState } from 'react';

import { type DisplayMode, DisplayModeContext } from './useDisplayMode';

const STORAGE_KEY = 'abacus:display-mode';

/** Read the stored preference; anything unexpected falls back to simple. */
function storedMode(): DisplayMode {
  try {
    return localStorage.getItem(STORAGE_KEY) === 'avance' ? 'avance' : 'simple';
  } catch {
    // Private mode / storage disabled: the preference simply does not persist.
    return 'simple';
  }
}

/**
 * Holds the simple/advanced reading level for the whole app. It is a *display*
 * preference, so it lives in the browser (per person, per device) and never gates
 * anything: what a user may see or do is decided by the server's permissions.
 */
export function DisplayModeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<DisplayMode>(storedMode);

  const setMode = useCallback((next: DisplayMode) => {
    setModeState(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // Not persisting is acceptable; the session-level choice still applies.
    }
  }, []);

  const value = useMemo(
    () => ({
      mode,
      isAdvanced: mode === 'avance',
      setMode,
      toggle: () => setMode(mode === 'avance' ? 'simple' : 'avance'),
    }),
    [mode, setMode]
  );

  return <DisplayModeContext.Provider value={value}>{children}</DisplayModeContext.Provider>;
}
