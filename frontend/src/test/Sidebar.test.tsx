import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { expect, it, vi } from 'vitest';

// Allow only the dashboard + reports; everything else must be greyed out.
const allowed = new Set(['dashboard:view', 'report:view']);
vi.mock('@/hooks/usePermissions', () => ({
  usePermissions: () => ({ has: (p: string) => allowed.has(p), isLoading: false }),
}));

vi.mock('@/components/layout/AssociationSwitcher', () => ({
  AssociationSwitcher: () => null,
}));

import { Sidebar } from '@/components/layout/Sidebar';

function renderSidebar() {
  return render(
    <MemoryRouter initialEntries={['/asso/A/synthese']}>
      <Routes>
        <Route path="/asso/:associationId/*" element={<Sidebar />} />
      </Routes>
    </MemoryRouter>
  );
}

it('links allowed pages and greys out the rest', () => {
  renderSidebar();

  // Allowed: real navigation links.
  expect(screen.getByRole('link', { name: /Synthèse/ })).toHaveAttribute(
    'href',
    '/asso/A/synthese'
  );
  expect(screen.getByRole('link', { name: /Journal/ })).toBeInTheDocument();

  // Forbidden pages are present but not links (greyed, aria-disabled).
  expect(screen.queryByRole('link', { name: /Saisie/ })).not.toBeInTheDocument();
  expect(screen.queryByRole('link', { name: /Tiers/ })).not.toBeInTheDocument();
  expect(screen.queryByRole('link', { name: /Paramètres/ })).not.toBeInTheDocument();

  const saisie = screen.getByText('Saisie').closest('[aria-disabled]');
  expect(saisie).toHaveAttribute('title', 'Accès non autorisé');
});
