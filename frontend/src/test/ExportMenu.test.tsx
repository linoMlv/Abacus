import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const triggerDownload = vi.fn();
vi.mock('@/lib/download', () => ({
  triggerDownload: (...args: unknown[]) => triggerDownload(...args),
}));

import { ExportMenu } from '@/components/ExportMenu';

const GROUPS = [
  {
    heading: 'Journal',
    items: [
      { label: 'Journal (PDF)', url: '/api/asso/A/exports/journal.pdf' },
      { label: 'Journal (Excel)', url: '/api/asso/A/exports/journal.xlsx' },
    ],
  },
];

beforeEach(() => {
  vi.clearAllMocks();
});

describe('ExportMenu', () => {
  it('downloads the selected export', async () => {
    render(<ExportMenu groups={GROUPS} />);

    await userEvent.click(screen.getByRole('button', { name: /Exporter/ }));
    await userEvent.click(await screen.findByText('Journal (Excel)'));

    expect(triggerDownload).toHaveBeenCalledWith('/api/asso/A/exports/journal.xlsx');
  });
});
