import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, it, vi } from 'vitest';

import DonutRepartition from '@/components/charts/DonutRepartition';
import type { DonutSlice } from '@/lib/chartColors';

const SLICES: DonutSlice[] = [
  { id: 'a', label: 'Fournitures', value: 300, color: '#2a78d6', isOther: false, ids: ['a'] },
  { id: 'b', label: 'Loyer', value: 100, color: '#1baf7a', isOther: false, ids: ['b'] },
];

it('renders a legend entry per slice with its share of the total', () => {
  render(<DonutRepartition slices={SLICES} total={400} centerLabel="Dépenses" />);
  expect(screen.getByText('Fournitures')).toBeInTheDocument();
  expect(screen.getByText('Loyer')).toBeInTheDocument();
  // 300 / 400 = 75 %, 100 / 400 = 25 %
  expect(screen.getByText('75 %')).toBeInTheDocument();
  expect(screen.getByText('25 %')).toBeInTheDocument();
});

it('calls onSelect with the slice when its legend entry is activated', async () => {
  const onSelect = vi.fn();
  render(
    <DonutRepartition slices={SLICES} total={400} centerLabel="Dépenses" onSelect={onSelect} />
  );
  await userEvent.click(screen.getByRole('button', { name: /Fournitures/ }));
  expect(onSelect).toHaveBeenCalledWith(SLICES[0]);
});

it('shows an empty hint and no legend when there is nothing to plot', () => {
  render(
    <DonutRepartition slices={[]} total={0} centerLabel="Dépenses" emptyHint="Rien à afficher" />
  );
  expect(screen.getByText('Rien à afficher')).toBeInTheDocument();
  expect(screen.queryByRole('button')).not.toBeInTheDocument();
});
