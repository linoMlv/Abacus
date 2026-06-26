import { Check, ChevronsUpDown, Plus } from 'lucide-react';
import { useNavigate, useParams } from 'react-router-dom';

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { useAuth } from '@/auth/useAuth';
import { ROLE_LABELS } from '@/lib/roles';
import { initials } from '@/lib/utils';

export function AssociationSwitcher() {
  const { session } = useAuth();
  const { associationId } = useParams();
  const navigate = useNavigate();

  const associations = session?.associations ?? [];
  const current = associations.find((a) => a.id === associationId);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="group flex w-full items-center gap-2.5 rounded-xl border border-hairline bg-surface px-2.5 py-2 text-left transition-colors hover:bg-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-ink text-xs font-semibold text-white">
          {initials(current?.name)}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium text-ink">
            {current?.name ?? 'Sélectionner'}
          </span>
          <span className="block truncate text-xs text-muted">
            {current ? ROLE_LABELS[current.role] : 'Aucune association'}
          </span>
        </span>
        <ChevronsUpDown className="h-4 w-4 shrink-0 text-faint" aria-hidden />
      </DropdownMenuTrigger>

      <DropdownMenuContent className="w-[15.5rem]">
        <DropdownMenuLabel>Vos associations</DropdownMenuLabel>
        {associations.map((a) => (
          <DropdownMenuItem key={a.id} onSelect={() => navigate(`/asso/${a.id}/synthese`)}>
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-hover text-[10px] font-semibold text-ink-soft">
              {initials(a.name)}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-ink">{a.name}</span>
              <span className="block truncate text-xs text-muted">{ROLE_LABELS[a.role]}</span>
            </span>
            {a.id === associationId && (
              <Check className="h-4 w-4 shrink-0 text-accent" aria-hidden />
            )}
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => navigate('/associations/nouvelle')}>
          <Plus className="h-4 w-4 shrink-0" aria-hidden />
          Créer une association
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
