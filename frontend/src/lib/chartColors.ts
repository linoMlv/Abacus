/**
 * Categorical colours for charts.
 *
 * Eight hues in a fixed order, validated for colour-vision deficiency on the app's
 * light surface (dataviz skill: worst adjacent CVD ΔE 24.2, well clear of the 12
 * floor). Colour follows the *entity* by its rank in a stable order and is never
 * cycled: a chart with more than eight entities folds its tail into a single
 * neutral "Autre" slice rather than reusing a hue. Three slots sit below 3:1
 * contrast on the surface, so any chart drawn from this palette ships visible
 * labels or a table view (the "relief" rule) — the donuts do both (legend + drill-down).
 */
export const CATEGORICAL = [
  '#2a78d6', // blue
  '#1baf7a', // aqua
  '#eda100', // yellow
  '#008300', // green
  '#4a3aa7', // violet
  '#e34948', // red
  '#e87ba4', // magenta
  '#eb6834', // orange
] as const;

/** Neutral (--color-faint) for the aggregated "Autre" slice — never a categorical hue. */
export const OTHER_COLOR = '#94a3b8';

/** Stable id of the folded "Autre" slice. */
export const OTHER_ID = '__other__';

/** Maximum number of marks a categorical chart shows before folding into "Autre". */
export const MAX_SLICES = CATEGORICAL.length;

export interface SliceInput {
  id: string;
  label: string;
  value: number;
}

export interface DonutSlice {
  id: string;
  label: string;
  value: number;
  color: string;
  isOther: boolean;
  /** Underlying entity ids: one for a normal slice, the whole tail for "Autre". */
  ids: string[];
}

/**
 * Turn magnitude rows into part-to-whole slices: drop non-positive values, sort by
 * descending magnitude, assign categorical hues in order, and fold anything beyond
 * the palette into one neutral "Autre" slice (its value is the sum of the tail).
 */
export function toSlices(rows: SliceInput[], max = MAX_SLICES): DonutSlice[] {
  const positive = rows.filter((r) => r.value > 0).sort((a, b) => b.value - a.value);
  if (positive.length === 0) return [];

  if (positive.length <= max) {
    return positive.map((r, i) => ({
      id: r.id,
      label: r.label,
      value: r.value,
      color: CATEGORICAL[i],
      isOther: false,
      ids: [r.id],
    }));
  }

  const leaders = positive.slice(0, max - 1);
  const tail = positive.slice(max - 1);
  const slices: DonutSlice[] = leaders.map((r, i) => ({
    id: r.id,
    label: r.label,
    value: r.value,
    color: CATEGORICAL[i],
    isOther: false,
    ids: [r.id],
  }));
  slices.push({
    id: OTHER_ID,
    label: 'Autre',
    value: tail.reduce((sum, r) => sum + r.value, 0),
    color: OTHER_COLOR,
    isOther: true,
    ids: tail.map((r) => r.id),
  });
  return slices;
}
