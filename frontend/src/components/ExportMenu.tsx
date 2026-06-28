import { ChevronDown, Download } from 'lucide-react';

import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { triggerDownload } from '@/lib/download';

export interface ExportItem {
  label: string;
  url: string;
}

export interface ExportGroup {
  heading: string;
  items: ExportItem[];
}

/** A small "Exporter" dropdown that downloads server-generated files. */
export function ExportMenu({
  groups,
  label = 'Exporter',
}: {
  groups: ExportGroup[];
  label?: string;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm">
          <Download className="h-4 w-4" aria-hidden />
          {label}
          <ChevronDown className="h-4 w-4 text-muted" aria-hidden />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {groups.map((group, index) => (
          <div key={group.heading}>
            {index > 0 && <DropdownMenuSeparator />}
            <DropdownMenuLabel>{group.heading}</DropdownMenuLabel>
            {group.items.map((item) => (
              <DropdownMenuItem key={item.label} onSelect={() => triggerDownload(item.url)}>
                {item.label}
              </DropdownMenuItem>
            ))}
          </div>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
