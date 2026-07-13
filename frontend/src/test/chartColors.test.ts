import { expect, it } from 'vitest';

import { CATEGORICAL, OTHER_COLOR, OTHER_ID, toSlices } from '@/lib/chartColors';

it('drops non-positive values and sorts slices by descending value', () => {
  const slices = toSlices([
    { id: 'a', label: 'A', value: 10 },
    { id: 'b', label: 'B', value: 0 },
    { id: 'c', label: 'C', value: 30 },
    { id: 'd', label: 'D', value: -5 },
  ]);
  expect(slices.map((s) => s.id)).toEqual(['c', 'a']);
  expect(slices.map((s) => s.value)).toEqual([30, 10]);
});

it('assigns categorical hues by fixed order, never cycled', () => {
  const slices = toSlices([
    { id: 'a', label: 'A', value: 30 },
    { id: 'b', label: 'B', value: 20 },
    { id: 'c', label: 'C', value: 10 },
  ]);
  expect(slices.map((s) => s.color)).toEqual([CATEGORICAL[0], CATEGORICAL[1], CATEGORICAL[2]]);
  expect(slices.every((s) => !s.isOther)).toBe(true);
});

it('keeps every entity coloured when the count fits the palette (8)', () => {
  const rows = Array.from({ length: 8 }, (_, i) => ({
    id: `id${i}`,
    label: `L${i}`,
    value: 8 - i,
  }));
  const slices = toSlices(rows);
  expect(slices).toHaveLength(8);
  expect(slices.some((s) => s.isOther)).toBe(false);
});

it('folds the tail into a single "Autre" slice beyond the palette', () => {
  const rows = Array.from({ length: 11 }, (_, i) => ({
    id: `id${i}`,
    label: `L${i}`,
    value: 100 - i, // strictly descending
  }));
  const slices = toSlices(rows);
  // 7 coloured leaders + 1 aggregated Autre = 8 marks (no hue is ever reused).
  expect(slices).toHaveLength(8);
  const other = slices[slices.length - 1];
  expect(other.isOther).toBe(true);
  expect(other.id).toBe(OTHER_ID);
  expect(other.color).toBe(OTHER_COLOR);
  // Autre carries the sum of the folded tail (ids 7..10 → values 93+92+91+90).
  expect(other.value).toBe(93 + 92 + 91 + 90);
  // …and keeps the tail's ids so the segment stays drillable.
  expect(other.ids).toEqual(['id7', 'id8', 'id9', 'id10']);
});

it('returns an empty list when nothing is positive', () => {
  expect(toSlices([{ id: 'a', label: 'A', value: 0 }])).toEqual([]);
});
