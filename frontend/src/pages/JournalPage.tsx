import { useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Check, Search, SlidersHorizontal, Trash2 } from 'lucide-react';
import { useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import { accountingApi } from '@/api/accounting';
import { ExportMenu } from '@/components/ExportMenu';
import { EcritureDrawer } from '@/components/journal/EcritureDrawer';
import { EmptyState } from '@/components/journal/EmptyState';
import { FilterPanel, ResetButton } from '@/components/journal/FilterPanel';
import { JournalSkeleton, JournalTable } from '@/components/journal/JournalTable';
import { Alert } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Sheet, SheetContent, SheetTitle } from '@/components/ui/sheet';
import { useJournalFilters } from '@/hooks/useJournalFilters';
import { usePermissions } from '@/hooks/usePermissions';
import { PERMISSIONS } from '@/lib/permissions';

/** Journal page size: entries load in batches via a "Charger plus" button. */
const PAGE_SIZE = 50;

export function JournalPage() {
  const { associationId } = useParams() as { associationId: string };
  const { has } = usePermissions();
  const queryClient = useQueryClient();
  const canExport = has(PERMISSIONS.REPORT_VIEW);
  const canCreate = has(PERMISSIONS.ENTRY_CREATE_SIMPLE);
  const canValidate = has(PERMISSIONS.ENTRY_VALIDATE);
  const canDelete = has(PERMISSIONS.ENTRY_DELETE);
  const canSelect = canValidate || canDelete;
  const navigate = useNavigate();

  const {
    filters,
    facets,
    activeCount,
    hasFilters,
    reset: resetFilters,
    dateFrom,
    dateTo,
    setDateFrom,
    setDateTo,
    search,
    setSearch,
  } = useJournalFilters(associationId);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  // Paginated, newest first: each page is a window of PAGE_SIZE rows. A full
  // page means there may be more (the cursor is the count loaded so far); a
  // short page is the end. Filters are part of the key, so changing one resets
  // the pagination from the first page.
  const ecrituresQuery = useInfiniteQuery({
    queryKey: ['ecritures', associationId, filters],
    queryFn: ({ pageParam }) =>
      accountingApi.listEcritures(associationId, {
        ...filters,
        limit: PAGE_SIZE,
        offset: pageParam,
      }),
    initialPageParam: 0,
    getNextPageParam: (lastPage, allPages) =>
      lastPage.length === PAGE_SIZE
        ? allPages.reduce((total, page) => total + page.length, 0)
        : undefined,
  });

  const rows = useMemo(() => ecrituresQuery.data?.pages.flat() ?? [], [ecrituresQuery.data]);

  // Bulk selection: kept as a set of ids, intersected with the visible rows so a
  // filter change never carries a stale, off-screen selection into an action.
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [confirmingBulkDelete, setConfirmingBulkDelete] = useState(false);
  const [bulkNotice, setBulkNotice] = useState<string | null>(null);
  const rowIds = useMemo(() => new Set(rows.map((r) => r.id)), [rows]);
  const selected = useMemo(() => selectedIds.filter((id) => rowIds.has(id)), [selectedIds, rowIds]);

  function toggleRow(id: string) {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  }
  function toggleAll() {
    // Decide from the *visible* rows, not the raw set (which may hold stale,
    // off-screen ids after a filter change): select all visible, or clear.
    setSelectedIds((prev) =>
      rows.length > 0 && rows.every((r) => prev.includes(r.id)) ? [] : rows.map((r) => r.id)
    );
  }
  function clearSelection() {
    setSelectedIds([]);
    setConfirmingBulkDelete(false);
  }

  const invalidateAfterBulk = () => {
    queryClient.invalidateQueries({ queryKey: ['ecritures', associationId] });
    queryClient.invalidateQueries({ queryKey: ['balance', associationId] });
    queryClient.invalidateQueries({ queryKey: ['synthese', associationId] });
  };

  function bulkSummary(verb: string, result: { traitees: string[]; ignorees: unknown[] }) {
    const ignored = result.ignorees.length;
    return ignored > 0
      ? `${result.traitees.length} ${verb}, ${ignored} ignorée${ignored > 1 ? 's' : ''}.`
      : `${result.traitees.length} ${verb}.`;
  }

  const bulkValidate = useMutation({
    mutationFn: (ids: string[]) => accountingApi.validerEcrituresGroupe(associationId, ids),
    onSuccess: (result) => {
      invalidateAfterBulk();
      clearSelection();
      setBulkNotice(bulkSummary('validée(s)', result));
    },
  });
  const bulkDelete = useMutation({
    mutationFn: (ids: string[]) => accountingApi.supprimerEcrituresGroupe(associationId, ids),
    onSuccess: (result) => {
      invalidateAfterBulk();
      clearSelection();
      setBulkNotice(bulkSummary('supprimée(s)', result));
    },
  });

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold tracking-tight text-ink">Journal</h2>
          <p className="mt-1 text-sm text-muted">
            Toutes les écritures de l’exercice, les plus récentes d’abord.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {canExport && (
            <ExportMenu
              label="Exporter"
              groups={[
                {
                  heading: 'Journal (filtres appliqués)',
                  items: [
                    {
                      label: 'Journal (PDF)',
                      url: accountingApi.journalPdfUrl(associationId, filters),
                    },
                    {
                      label: 'Journal (Excel)',
                      url: accountingApi.journalXlsxUrl(associationId, filters),
                    },
                  ],
                },
              ]}
            />
          )}
          {canCreate && (
            <Button variant="accent" onClick={() => navigate(`/asso/${associationId}/saisie`)}>
              Nouvelle opération
            </Button>
          )}
        </div>
      </div>

      <div className="lg:grid lg:grid-cols-[15rem_minmax(0,1fr)] lg:gap-6">
        {/* Faceted filters: a sidebar on desktop, a drawer on small screens. */}
        <aside className="hidden lg:block">
          <Card className="sticky top-6 p-4">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-ink">Filtres</h3>
              {activeCount > 0 && <ResetButton onClick={resetFilters} />}
            </div>
            <FilterPanel
              facets={facets}
              dateFrom={dateFrom}
              dateTo={dateTo}
              onDateFrom={setDateFrom}
              onDateTo={setDateTo}
            />
          </Card>
        </aside>

        <div className="mt-4 min-w-0 space-y-4 lg:mt-0">
          <div className="flex items-center gap-2">
            <div className="relative min-w-0 flex-1">
              <Search
                className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-faint"
                aria-hidden
              />
              <Input
                aria-label="Rechercher dans les libellés"
                placeholder="Rechercher un libellé…"
                className="pl-9"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
            <button
              type="button"
              onClick={() => setDrawerOpen(true)}
              className="relative inline-flex shrink-0 items-center gap-2 rounded-lg border border-hairline bg-surface px-3 py-2 text-sm font-medium text-ink hover:bg-hover lg:hidden"
            >
              <SlidersHorizontal className="h-4 w-4" aria-hidden />
              Filtres
              {activeCount > 0 && (
                <span className="inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-accent px-1 text-[11px] font-semibold text-white">
                  {activeCount}
                </span>
              )}
            </button>
          </div>

          {bulkNotice && (
            <div
              role="status"
              className="rounded-lg border border-recette/20 bg-recette-soft px-3.5 py-2.5 text-sm text-recette"
            >
              {bulkNotice}
            </div>
          )}

          {canSelect && selected.length > 0 && (
            <div className="flex flex-wrap items-center gap-2 rounded-lg border border-accent/30 bg-accent-soft px-4 py-2.5 text-sm">
              {confirmingBulkDelete ? (
                <>
                  <span className="flex-1 font-medium text-ink">
                    Supprimer {selected.length} écriture{selected.length > 1 ? 's' : ''} ?
                    (brouillons uniquement)
                  </span>
                  <Button variant="ghost" size="sm" onClick={() => setConfirmingBulkDelete(false)}>
                    Annuler
                  </Button>
                  <Button
                    variant="danger"
                    size="sm"
                    disabled={bulkDelete.isPending}
                    onClick={() => bulkDelete.mutate(selected)}
                  >
                    Confirmer la suppression
                  </Button>
                </>
              ) : (
                <>
                  <span className="flex-1 font-medium text-ink">
                    {selected.length} sélectionnée{selected.length > 1 ? 's' : ''}
                  </span>
                  {canValidate && (
                    <Button
                      variant="accent"
                      size="sm"
                      disabled={bulkValidate.isPending}
                      onClick={() => bulkValidate.mutate(selected)}
                    >
                      <Check className="h-4 w-4" aria-hidden />
                      Valider la sélection
                    </Button>
                  )}
                  {canDelete && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setConfirmingBulkDelete(true)}
                    >
                      <Trash2 className="h-4 w-4" aria-hidden />
                      Supprimer la sélection
                    </Button>
                  )}
                  <button
                    type="button"
                    onClick={clearSelection}
                    className="text-xs font-medium text-muted hover:text-ink"
                  >
                    Désélectionner
                  </button>
                </>
              )}
            </div>
          )}

          {ecrituresQuery.isError ? (
            <Alert>Impossible de charger les écritures.</Alert>
          ) : ecrituresQuery.isLoading ? (
            <JournalSkeleton />
          ) : rows.length === 0 ? (
            <EmptyState associationId={associationId} filtered={hasFilters} />
          ) : (
            <>
              <JournalTable
                associationId={associationId}
                rows={rows}
                onSelect={setSelectedId}
                selectable={canSelect}
                selectedIds={selected}
                onToggleRow={toggleRow}
                onToggleAll={toggleAll}
              />
              {ecrituresQuery.hasNextPage && (
                <div className="flex justify-center">
                  <Button
                    variant="outline"
                    disabled={ecrituresQuery.isFetchingNextPage}
                    onClick={() => ecrituresQuery.fetchNextPage()}
                  >
                    {ecrituresQuery.isFetchingNextPage ? 'Chargement…' : 'Charger plus'}
                  </Button>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
        <SheetContent className="lg:hidden">
          <div className="flex items-center justify-between border-b border-hairline p-4 pr-12">
            <SheetTitle>Filtres</SheetTitle>
            {activeCount > 0 && <ResetButton onClick={resetFilters} />}
          </div>
          <div className="flex-1 overflow-y-auto p-4">
            <FilterPanel
              facets={facets}
              dateFrom={dateFrom}
              dateTo={dateTo}
              onDateFrom={setDateFrom}
              onDateTo={setDateTo}
            />
          </div>
        </SheetContent>
      </Sheet>

      {selectedId && (
        <EcritureDrawer
          associationId={associationId}
          ecritureId={selectedId}
          onClose={() => setSelectedId(null)}
        />
      )}
    </div>
  );
}
