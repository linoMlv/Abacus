import type { SyntheseParams } from '@/api/accounting';

export type Preset = 'mois' | 'trimestre' | 'exercice' | 'custom';

export const PRESET_LABELS: Record<Preset, string> = {
  mois: 'Mois',
  trimestre: 'Trimestre',
  exercice: 'Exercice',
  custom: 'Personnalisé',
};

function ymd(year: number, month1: number, day: number): string {
  return `${year}-${String(month1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
}

/** Period parameters for a preset (exercice → empty: the server uses the open one). */
export function presetParams(preset: Preset, customFrom: string, customTo: string): SyntheseParams {
  const now = new Date();
  const year = now.getFullYear();
  if (preset === 'mois') {
    const m = now.getMonth(); // 0-based
    const last = new Date(year, m + 1, 0).getDate();
    return { date_from: ymd(year, m + 1, 1), date_to: ymd(year, m + 1, last) };
  }
  if (preset === 'trimestre') {
    const start = Math.floor(now.getMonth() / 3) * 3; // 0-based first month
    const last = new Date(year, start + 3, 0).getDate();
    return { date_from: ymd(year, start + 1, 1), date_to: ymd(year, start + 3, last) };
  }
  if (preset === 'custom') {
    return customFrom && customTo ? { date_from: customFrom, date_to: customTo } : {};
  }
  return {}; // exercice
}
