import { NavLink, useParams } from 'react-router-dom';

import { BrandWordmark } from '@/components/Brand';
import { NAV_SECTIONS, SETTINGS_ITEM, type NavItem } from '@/lib/nav';
import { cn } from '@/lib/utils';

import { AssociationSwitcher } from './AssociationSwitcher';

function NavRow({ item, base, onNavigate }: NavRowProps) {
  const Icon = item.icon;
  return (
    <NavLink
      to={`${base}/${item.segment}`}
      onClick={onNavigate}
      className={({ isActive }) =>
        cn(
          'group relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
          isActive ? 'bg-accent-soft text-accent' : 'text-ink-soft hover:bg-hover hover:text-ink'
        )
      }
    >
      {({ isActive }) => (
        <>
          {isActive && (
            <span className="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r-full bg-accent" />
          )}
          <Icon
            className={cn(
              'h-[18px] w-[18px] shrink-0',
              isActive ? 'text-accent' : 'text-faint group-hover:text-muted'
            )}
            aria-hidden
          />
          {item.label}
        </>
      )}
    </NavLink>
  );
}

interface NavRowProps {
  item: NavItem;
  base: string;
  onNavigate?: () => void;
}

export function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { associationId } = useParams();
  const base = `/asso/${associationId}`;

  return (
    <aside className="flex h-dvh w-64 shrink-0 flex-col border-r border-hairline bg-surface">
      <div className="px-5 py-5">
        <BrandWordmark />
      </div>
      <div className="px-3 pb-3">
        <AssociationSwitcher />
      </div>

      <nav className="flex-1 overflow-y-auto px-3 pb-4">
        {NAV_SECTIONS.map((section) => (
          <div key={section.label ?? 'main'} className="mb-5">
            {section.label && (
              <p className="px-3 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-faint">
                {section.label}
              </p>
            )}
            <div className="space-y-0.5">
              {section.items.map((item) => (
                <NavRow key={item.segment} item={item} base={base} onNavigate={onNavigate} />
              ))}
            </div>
          </div>
        ))}
      </nav>

      <div className="border-t border-hairline px-3 py-3">
        <NavRow item={SETTINGS_ITEM} base={base} onNavigate={onNavigate} />
      </div>
    </aside>
  );
}
