import { useMutation } from '@tanstack/react-query';
import { LogOut } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { authApi } from '@/api/auth';
import { useAuth } from '@/auth/useAuth';
import { initials } from '@/lib/utils';

export function UserMenu() {
  const { session, refresh } = useAuth();
  const navigate = useNavigate();
  const user = session?.user;

  const logout = useMutation({
    mutationFn: authApi.logout,
    onSettled: () => {
      refresh();
      navigate('/login', { replace: true });
    },
  });

  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="flex h-9 w-9 items-center justify-center rounded-full bg-ink text-xs font-semibold text-white transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-canvas">
        {initials(user?.name)}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-[15rem]">
        <div className="px-2.5 py-1.5">
          <p className="truncate text-sm font-medium text-ink">{user?.name}</p>
          <p className="truncate text-xs text-muted">{user?.email}</p>
        </div>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => logout.mutate()}>
          <LogOut className="h-4 w-4 shrink-0" aria-hidden />
          Se déconnecter
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
