import { Menu } from 'lucide-react';
import { useLocation } from 'react-router-dom';

import { ALL_NAV_ITEMS } from '@/lib/nav';

import { UserMenu } from './UserMenu';

function currentTitle(pathname: string): string {
  const segment = pathname.split('/').filter(Boolean).pop();
  return ALL_NAV_ITEMS.find((item) => item.segment === segment)?.label ?? '';
}

export function Topbar({ onMenu }: { onMenu: () => void }) {
  const { pathname } = useLocation();

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-hairline bg-canvas/80 px-6 backdrop-blur lg:px-8">
      <button
        type="button"
        onClick={onMenu}
        aria-label="Ouvrir la navigation"
        className="-ml-1 flex h-9 w-9 items-center justify-center rounded-lg text-ink-soft hover:bg-hover lg:hidden"
      >
        <Menu className="h-5 w-5" aria-hidden />
      </button>
      <h1 className="text-[15px] font-semibold text-ink">{currentTitle(pathname)}</h1>
      <div className="ml-auto">
        <UserMenu />
      </div>
    </header>
  );
}
