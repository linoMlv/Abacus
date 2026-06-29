import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Check,
  ChevronDown,
  Eye,
  Paperclip,
  Search,
  SlidersHorizontal,
  Trash2,
  X,
} from 'lucide-react';
import {
  type Dispatch,
  type ReactNode,
  type SetStateAction,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import {
  accountingApi,
  type EcritureListItem,
  type EcritureStatut,
  type Justificatif,
  JUSTIFICATIF_ACCEPT,
  JUSTIFICATIF_MAX_BYTES,
  type TypeOperation,
  TYPE_OPERATION_LABELS,
} from '@/api/accounting';
import { apiErrorMessage } from '@/api/client';
import { ExportMenu } from '@/components/ExportMenu';
import { JustificatifViewer } from '@/components/JustificatifViewer';
import { Alert } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Sheet, SheetContent, SheetTitle } from '@/components/ui/sheet';
import { usePermissions } from '@/hooks/usePermissions';
import { formatAmount, formatBytes, formatDate, formatEUR } from '@/lib/format';
import { PERMISSIONS } from '@/lib/permissions';
import { cn } from '@/lib/utils';

const STATUT_LABELS: Record<EcritureStatut, string> = {
  brouillon: 'Brouillon',
  validee: 'Validée',
};

interface FilterOption {
  value: string;
  label: string;
}

interface Facet {
  key: string;
  title: string;
  options: FilterOption[];
  selected: string[];
  onToggle: (value: string) => void;
  /** Cap the list height with an inner scroll (for potentially long lists). */
  scroll?: boolean;
}

const TYPE_OPTIONS: FilterOption[] = (['recette', 'depense', 'virement'] as const).map((v) => ({
  value: v,
  label: TYPE_OPERATION_LABELS[v],
}));

const STATUT_OPTIONS: FilterOption[] = (['brouillon', 'validee'] as const).map((v) => ({
  value: v,
  label: STATUT_LABELS[v],
}));

function toggleValue<T>(setter: Dispatch<SetStateAction<T[]>>, value: T) {
  setter((prev) => (prev.includes(value) ? prev.filter((v) => v !== value) : [...prev, value]));
}

function StatutBadge({ statut }: { statut: EcritureStatut }) {
  return (
    <Badge variant={statut === 'validee' ? 'accent' : 'warning'}>{STATUT_LABELS[statut]}</Badge>
  );
}

/** Debounce a fast-changing value (e.g. a search box) before it hits the API. */
function useDebounced<T>(value: T, delayMs = 250): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(id);
  }, [value, delayMs]);
  return debounced;
}

export function JournalPage() {
  const { associationId } = useParams() as { associationId: string };
  const { has } = usePermissions();
  const canExport = has(PERMISSIONS.REPORT_VIEW);
  const canCreate = has(PERMISSIONS.ENTRY_CREATE_SIMPLE);
  const navigate = useNavigate();

  const [statuts, setStatuts] = useState<EcritureStatut[]>([]);
  const [journalIds, setJournalIds] = useState<string[]>([]);
  const [compteIds, setCompteIds] = useState<string[]>([]);
  const [typeOperations, setTypeOperations] = useState<TypeOperation[]>([]);
  const [categorieIds, setCategorieIds] = useState<string[]>([]);
  const [tiersIds, setTiersIds] = useState<string[]>([]);
  const [evenementIds, setEvenementIds] = useState<string[]>([]);
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [search, setSearch] = useState('');
  const q = useDebounced(search);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const journauxQuery = useQuery({
    queryKey: ['journaux', associationId],
    queryFn: () => accountingApi.listJournaux(associationId),
  });

  const tresorerieQuery = useQuery({
    queryKey: ['tresorerie', associationId],
    queryFn: () => accountingApi.listTresorerie(associationId),
  });

  const categoriesQuery = useQuery({
    queryKey: ['categories', associationId],
    queryFn: () => accountingApi.listCategories(associationId),
  });

  const tiersQuery = useQuery({
    queryKey: ['tiers', associationId],
    queryFn: () => accountingApi.listTiers(associationId),
  });

  const evenementsQuery = useQuery({
    queryKey: ['evenements', associationId],
    queryFn: () => accountingApi.listEvenements(associationId),
  });

  const ecrituresQuery = useQuery({
    queryKey: [
      'ecritures',
      associationId,
      {
        statuts,
        journalIds,
        compteIds,
        typeOperations,
        categorieIds,
        tiersIds,
        evenementIds,
        dateFrom,
        dateTo,
        q,
      },
    ],
    queryFn: () =>
      accountingApi.listEcritures(associationId, {
        statut: statuts.length ? statuts : undefined,
        journal_id: journalIds.length ? journalIds : undefined,
        compte_id: compteIds.length ? compteIds : undefined,
        type_operation: typeOperations.length ? typeOperations : undefined,
        categorie_id: categorieIds.length ? categorieIds : undefined,
        tiers_id: tiersIds.length ? tiersIds : undefined,
        evenement_id: evenementIds.length ? evenementIds : undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        q: q || undefined,
      }),
  });

  const rows = ecrituresQuery.data ?? [];

  const facets: Facet[] = [
    {
      key: 'type',
      title: 'Type',
      options: TYPE_OPTIONS,
      selected: typeOperations,
      onToggle: (v) => toggleValue(setTypeOperations, v as TypeOperation),
    },
    {
      key: 'statut',
      title: 'Statut',
      options: STATUT_OPTIONS,
      selected: statuts,
      onToggle: (v) => toggleValue(setStatuts, v as EcritureStatut),
    },
    {
      key: 'journal',
      title: 'Journal',
      options: (journauxQuery.data ?? []).map((j) => ({
        value: j.id,
        label: `${j.code} — ${j.libelle}`,
      })),
      selected: journalIds,
      onToggle: (v) => toggleValue(setJournalIds, v),
    },
    {
      key: 'compte',
      title: 'Compte de trésorerie',
      options: (tresorerieQuery.data ?? []).map((c) => ({ value: c.id, label: c.libelle })),
      selected: compteIds,
      onToggle: (v) => toggleValue(setCompteIds, v),
      scroll: true,
    },
    {
      key: 'categorie',
      title: 'Catégorie',
      options: (categoriesQuery.data ?? []).map((c) => ({ value: c.id, label: c.libelle })),
      selected: categorieIds,
      onToggle: (v) => toggleValue(setCategorieIds, v),
      scroll: true,
    },
    {
      key: 'tiers',
      title: 'Tiers',
      options: (tiersQuery.data ?? []).map((t) => ({ value: t.id, label: t.nom })),
      selected: tiersIds,
      onToggle: (v) => toggleValue(setTiersIds, v),
      scroll: true,
    },
    {
      key: 'evenement',
      title: 'Événement',
      options: (evenementsQuery.data ?? []).map((e) => ({ value: e.id, label: e.nom })),
      selected: evenementIds,
      onToggle: (v) => toggleValue(setEvenementIds, v),
      scroll: true,
    },
  ];

  const activeCount =
    typeOperations.length +
    statuts.length +
    journalIds.length +
    compteIds.length +
    categorieIds.length +
    tiersIds.length +
    evenementIds.length +
    (dateFrom ? 1 : 0) +
    (dateTo ? 1 : 0);
  const hasFilters = activeCount > 0 || q !== '';

  function resetFilters() {
    setStatuts([]);
    setJournalIds([]);
    setCompteIds([]);
    setTypeOperations([]);
    setCategorieIds([]);
    setTiersIds([]);
    setEvenementIds([]);
    setDateFrom('');
    setDateTo('');
    setSearch('');
  }

  // Exports follow the date range from the filters (the export endpoints scope
  // by period; the facet filters are a future enhancement on the export side).
  const exportParams = { date_from: dateFrom || undefined, date_to: dateTo || undefined };

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
              groups={[
                {
                  heading: 'Journal',
                  items: [
                    {
                      label: 'Journal (PDF)',
                      url: accountingApi.journalPdfUrl(associationId, exportParams),
                    },
                    {
                      label: 'Journal (Excel)',
                      url: accountingApi.journalXlsxUrl(associationId, exportParams),
                    },
                  ],
                },
                {
                  heading: 'Grand livre',
                  items: [
                    {
                      label: 'Grand livre (PDF)',
                      url: accountingApi.grandLivrePdfUrl(associationId, exportParams),
                    },
                    {
                      label: 'Grand livre (Excel)',
                      url: accountingApi.grandLivreXlsxUrl(associationId, exportParams),
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
          <Card className="sticky top-6 max-h-[calc(100dvh-3rem)] overflow-y-auto p-4">
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

          {ecrituresQuery.isError ? (
            <Alert>Impossible de charger les écritures.</Alert>
          ) : rows.length === 0 ? (
            <EmptyState associationId={associationId} filtered={hasFilters} />
          ) : (
            <JournalTable rows={rows} onSelect={setSelectedId} />
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

function ResetButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex items-center gap-1 text-xs font-medium text-muted hover:text-ink"
    >
      <X className="h-3.5 w-3.5" aria-hidden />
      Réinitialiser
    </button>
  );
}

function FilterGroup({
  title,
  count,
  children,
}: {
  title: string;
  count?: number;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(true);
  return (
    <section className="border-t border-hairline pt-4 first:border-0 first:pt-0">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((prev) => !prev)}
        className="flex w-full items-center gap-2 text-xs font-semibold uppercase tracking-wider text-faint transition-colors hover:text-muted"
      >
        <ChevronDown
          className={cn('h-3.5 w-3.5 shrink-0 transition-transform', !open && '-rotate-90')}
          aria-hidden
        />
        <span className="flex-1 text-left">{title}</span>
        {count ? (
          <span className="inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-accent-soft px-1 text-[10px] font-semibold normal-case text-accent">
            {count}
          </span>
        ) : null}
      </button>
      {open && <div className="mt-2">{children}</div>}
    </section>
  );
}

function FacetSection({ facet }: { facet: Facet }) {
  if (facet.options.length === 0) return null;
  return (
    <FilterGroup title={facet.title} count={facet.selected.length}>
      <ul className={cn('space-y-0.5', facet.scroll && 'max-h-44 overflow-y-auto')}>
        {facet.options.map((option) => (
          <li key={option.value}>
            <label className="flex cursor-pointer items-center gap-2.5 rounded-md px-1 py-1.5 text-sm text-ink hover:bg-hover">
              <input
                type="checkbox"
                className="h-4 w-4 shrink-0 rounded border-hairline accent-accent"
                checked={facet.selected.includes(option.value)}
                onChange={() => facet.onToggle(option.value)}
              />
              <span className="min-w-0 truncate">{option.label}</span>
            </label>
          </li>
        ))}
      </ul>
    </FilterGroup>
  );
}

function FilterPanel({
  facets,
  dateFrom,
  dateTo,
  onDateFrom,
  onDateTo,
}: {
  facets: Facet[];
  dateFrom: string;
  dateTo: string;
  onDateFrom: (value: string) => void;
  onDateTo: (value: string) => void;
}) {
  return (
    <div className="space-y-4">
      <FilterGroup title="Période">
        <div className="space-y-2.5">
          <div>
            <label htmlFor="filtre-date-from" className="text-xs text-muted">
              Du
            </label>
            <Input
              id="filtre-date-from"
              type="date"
              aria-label="Date de début"
              className="mt-1"
              value={dateFrom}
              max={dateTo || undefined}
              onChange={(e) => onDateFrom(e.target.value)}
            />
          </div>
          <div>
            <label htmlFor="filtre-date-to" className="text-xs text-muted">
              Au
            </label>
            <Input
              id="filtre-date-to"
              type="date"
              aria-label="Date de fin"
              className="mt-1"
              value={dateTo}
              min={dateFrom || undefined}
              onChange={(e) => onDateTo(e.target.value)}
            />
          </div>
        </div>
      </FilterGroup>
      {facets.map((facet) => (
        <FacetSection key={facet.key} facet={facet} />
      ))}
    </div>
  );
}

function EmptyState({ associationId, filtered }: { associationId: string; filtered: boolean }) {
  const navigate = useNavigate();
  return (
    <Card className="flex flex-col items-center gap-3 px-6 py-14 text-center">
      <h3 className="text-base font-semibold text-ink">
        {filtered ? 'Aucune écriture ne correspond' : 'Aucune écriture pour l’instant'}
      </h3>
      <p className="max-w-sm text-sm text-muted">
        {filtered
          ? 'Ajustez les filtres pour élargir la recherche.'
          : 'Enregistrez une première recette ou dépense ; elle apparaîtra ici.'}
      </p>
      {!filtered && (
        <Button variant="accent" onClick={() => navigate(`/asso/${associationId}/saisie`)}>
          Saisir une opération
        </Button>
      )}
    </Card>
  );
}

function JournalTable({
  rows,
  onSelect,
}: {
  rows: EcritureListItem[];
  onSelect: (id: string) => void;
}) {
  return (
    <Card className="overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[34rem] text-sm">
          <thead>
            <tr className="border-b border-hairline text-left text-xs uppercase tracking-wider text-faint">
              <th className="px-4 py-2.5 font-medium">Date</th>
              <th className="px-4 py-2.5 font-medium">Pièce</th>
              <th className="px-4 py-2.5 font-medium">Journal</th>
              <th className="px-4 py-2.5 font-medium">Libellé</th>
              <th className="px-4 py-2.5 text-right font-medium">Montant</th>
              <th className="px-4 py-2.5 font-medium">Statut</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((e) => (
              <tr
                key={e.id}
                onClick={() => onSelect(e.id)}
                className="cursor-pointer border-b border-hairline last:border-0 hover:bg-hover"
              >
                <td className="whitespace-nowrap px-4 py-2.5 text-muted">{formatDate(e.date)}</td>
                <td className="px-4 py-2.5 font-mono text-xs tabular-nums text-muted">
                  {e.numero_piece}
                </td>
                <td className="px-4 py-2.5">
                  <Badge variant="neutral">{e.journal_code}</Badge>
                </td>
                <td className="px-4 py-2.5 text-ink">{e.libelle}</td>
                <td className="px-4 py-2.5 text-right font-mono tabular-nums text-ink">
                  {formatEUR(e.montant)}
                </td>
                <td className="px-4 py-2.5">
                  <StatutBadge statut={e.statut} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

/** Justificatifs of an entry: list, preview, upload (PDF/image, 5 Mo), delete. */
function JustificatifsSection({
  associationId,
  ecritureId,
}: {
  associationId: string;
  ecritureId: string;
}) {
  const queryClient = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const [localError, setLocalError] = useState<string | null>(null);
  const [viewing, setViewing] = useState<Justificatif | null>(null);
  const { has } = usePermissions();
  const canManage = has(PERMISSIONS.ATTACHMENT_MANAGE);

  const listQuery = useQuery({
    queryKey: ['justificatifs', associationId, ecritureId],
    queryFn: () => accountingApi.listJustificatifs(associationId, ecritureId),
  });

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ['justificatifs', associationId, ecritureId] });

  const upload = useMutation({
    mutationFn: (file: File) => accountingApi.uploadJustificatif(associationId, ecritureId, file),
    onSuccess: invalidate,
  });
  const remove = useMutation({
    mutationFn: (id: string) => accountingApi.supprimerJustificatif(associationId, id),
    onSuccess: invalidate,
  });

  function onPick(e: React.ChangeEvent<HTMLInputElement>) {
    setLocalError(null);
    const file = e.target.files?.[0];
    e.target.value = ''; // allow re-picking the same file
    if (!file) return;
    // The server re-validates type and size — this is just a friendlier guard.
    if (file.size > JUSTIFICATIF_MAX_BYTES) {
      setLocalError('Fichier trop volumineux (5 Mo maximum).');
      return;
    }
    upload.mutate(file);
  }

  const items = listQuery.data ?? [];
  const error =
    localError ??
    apiErrorMessage(upload, 'Envoi du justificatif impossible.') ??
    apiErrorMessage(remove, 'Suppression impossible.');

  return (
    <section className="space-y-2 border-t border-hairline pt-4">
      <div className="flex items-center justify-between">
        <h4 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-faint">
          <Paperclip className="h-3.5 w-3.5" aria-hidden />
          Justificatifs
        </h4>
        {canManage && (
          <>
            <input
              ref={inputRef}
              type="file"
              accept={JUSTIFICATIF_ACCEPT}
              className="sr-only"
              onChange={onPick}
              aria-label="Ajouter un justificatif"
            />
            <Button
              variant="outline"
              size="sm"
              disabled={upload.isPending}
              onClick={() => inputRef.current?.click()}
            >
              {upload.isPending ? 'Envoi…' : 'Ajouter'}
            </Button>
          </>
        )}
      </div>

      {error && <Alert>{error}</Alert>}

      {items.length === 0 ? (
        <p className="text-xs text-muted">Aucun justificatif (PDF ou image, 5 Mo max).</p>
      ) : (
        <ul className="space-y-1.5">
          {items.map((j) => (
            <li
              key={j.id}
              className="flex items-center gap-2 rounded-lg border border-hairline px-3 py-2 text-sm"
            >
              <button
                type="button"
                onClick={() => setViewing(j)}
                className="flex min-w-0 flex-1 items-center gap-2 text-left"
                aria-label={`Aperçu de ${j.filename}`}
              >
                <Eye className="h-4 w-4 shrink-0 text-muted" aria-hidden />
                <span className="min-w-0 flex-1 truncate text-ink hover:text-accent">
                  {j.filename}
                </span>
              </button>
              <span className="shrink-0 text-xs text-faint">{formatBytes(j.size)}</span>
              {canManage && (
                <button
                  type="button"
                  onClick={() => remove.mutate(j.id)}
                  disabled={remove.isPending}
                  className="shrink-0 rounded-md p-1 text-faint hover:bg-hover hover:text-depense"
                  aria-label={`Supprimer ${j.filename}`}
                >
                  <Trash2 className="h-4 w-4" aria-hidden />
                </button>
              )}
            </li>
          ))}
        </ul>
      )}

      <JustificatifViewer
        associationId={associationId}
        justificatif={viewing}
        open={viewing !== null}
        onOpenChange={(o) => !o && setViewing(null)}
      />
    </section>
  );
}

function EcritureDrawer({
  associationId,
  ecritureId,
  onClose,
}: {
  associationId: string;
  ecritureId: string;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const { has } = usePermissions();
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const detailQuery = useQuery({
    queryKey: ['ecriture', associationId, ecritureId],
    queryFn: () => accountingApi.getEcriture(associationId, ecritureId),
  });
  const comptesQuery = useQuery({
    queryKey: ['comptes', associationId],
    queryFn: () => accountingApi.listComptes(associationId),
  });

  const compteLabel = useMemo(() => {
    const byId = new Map((comptesQuery.data ?? []).map((c) => [c.id, c]));
    return (id: string) => {
      const c = byId.get(id);
      return c ? `${c.numero} — ${c.libelle}` : id;
    };
  }, [comptesQuery.data]);

  const invalidateLists = () => {
    queryClient.invalidateQueries({ queryKey: ['ecritures', associationId] });
    queryClient.invalidateQueries({ queryKey: ['balance', associationId] });
  };

  const validate = useMutation({
    mutationFn: () => accountingApi.validerEcriture(associationId, ecritureId),
    onSuccess: () => {
      invalidateLists();
      queryClient.invalidateQueries({ queryKey: ['ecriture', associationId, ecritureId] });
    },
  });
  const remove = useMutation({
    mutationFn: () => accountingApi.supprimerEcriture(associationId, ecritureId),
    onSuccess: () => {
      invalidateLists();
      onClose();
    },
  });

  const entry = detailQuery.data;
  const isDraft = entry?.statut === 'brouillon';
  const canValidate = has(PERMISSIONS.ENTRY_VALIDATE);
  const canDelete = has(PERMISSIONS.ENTRY_DELETE);
  const actionError =
    apiErrorMessage(validate, 'Validation impossible.') ??
    apiErrorMessage(remove, 'Suppression impossible.');

  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      <button
        type="button"
        aria-label="Fermer"
        className="absolute inset-0 bg-ink/20"
        onClick={onClose}
      />
      <aside
        role="dialog"
        aria-modal="true"
        aria-label="Détail de l’écriture"
        className="relative flex h-full w-full max-w-md flex-col bg-surface shadow-xl"
      >
        <header className="flex items-center justify-between border-b border-hairline px-5 py-4">
          <h3 className="text-base font-semibold text-ink">
            {entry ? `Pièce n° ${entry.numero_piece}` : 'Détail'}
          </h3>
          <Button variant="ghost" size="icon" onClick={onClose} aria-label="Fermer">
            <X className="h-4 w-4" aria-hidden />
          </Button>
        </header>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          {detailQuery.isError && <Alert>Écriture introuvable.</Alert>}
          {entry && (
            <div className="space-y-4">
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted">{formatDate(entry.date)}</span>
                <StatutBadge statut={entry.statut} />
              </div>
              <p className="text-sm text-ink">{entry.libelle}</p>

              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-hairline text-left text-xs uppercase tracking-wider text-faint">
                    <th className="py-2 font-medium">Compte</th>
                    <th className="py-2 text-right font-medium">Débit</th>
                    <th className="py-2 text-right font-medium">Crédit</th>
                  </tr>
                </thead>
                <tbody>
                  {entry.lignes.map((l) => (
                    <tr key={l.id} className="border-b border-hairline last:border-0">
                      <td className="py-2 pr-2 text-ink">{compteLabel(l.compte_id)}</td>
                      <td className="py-2 text-right font-mono tabular-nums text-ink">
                        {Number(l.debit) > 0 ? formatAmount(l.debit) : ''}
                      </td>
                      <td className="py-2 text-right font-mono tabular-nums text-ink">
                        {Number(l.credit) > 0 ? formatAmount(l.credit) : ''}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <JustificatifsSection associationId={associationId} ecritureId={ecritureId} />
            </div>
          )}
        </div>

        {entry && (
          <footer className="space-y-3 border-t border-hairline px-5 py-4">
            {actionError && <Alert>{actionError}</Alert>}
            {!isDraft ? (
              <p className="text-xs text-muted">
                Écriture validée : immuable (une correction passe par contre-passation).
              </p>
            ) : confirmingDelete ? (
              <div className="flex items-center gap-2">
                <span className="flex-1 text-sm text-ink">Supprimer ce brouillon ?</span>
                <Button variant="ghost" onClick={() => setConfirmingDelete(false)}>
                  Annuler
                </Button>
                <Button
                  variant="danger"
                  disabled={remove.isPending}
                  onClick={() => remove.mutate()}
                >
                  Confirmer
                </Button>
              </div>
            ) : (
              <div className="flex gap-2">
                {canValidate && (
                  <Button
                    variant="accent"
                    className="flex-1"
                    disabled={validate.isPending}
                    onClick={() => validate.mutate()}
                  >
                    <Check className="h-4 w-4" aria-hidden />
                    Valider
                  </Button>
                )}
                {canDelete && (
                  <Button variant="outline" onClick={() => setConfirmingDelete(true)}>
                    <Trash2 className="h-4 w-4" aria-hidden />
                    Supprimer
                  </Button>
                )}
              </div>
            )}
          </footer>
        )}
      </aside>
    </div>
  );
}
