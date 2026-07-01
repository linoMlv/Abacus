import { useQuery } from '@tanstack/react-query';
import { type Dispatch, type SetStateAction, useMemo, useState } from 'react';

import {
  accountingApi,
  type EcritureStatut,
  type JournalFilters,
  type TypeOperation,
  TYPE_OPERATION_LABELS,
} from '@/api/accounting';
import { STATUT_LABELS, type Facet, type FilterOption } from '@/components/journal/types';

import { useDebounced } from './useDebounced';

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

/** All journal filter state: the facets, the server filter payload and reset. */
export interface JournalFilterState {
  filters: JournalFilters;
  facets: Facet[];
  activeCount: number;
  hasFilters: boolean;
  reset: () => void;
  dateFrom: string;
  dateTo: string;
  setDateFrom: (value: string) => void;
  setDateTo: (value: string) => void;
  search: string;
  setSearch: (value: string) => void;
}

/**
 * Owns the journal's faceted filter state and the reference lists that populate
 * the facets. Returns the server filter payload (debounced search included) plus
 * the facets ready for the {@link FilterPanel}.
 */
export function useJournalFilters(associationId: string): JournalFilterState {
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

  // The active filter, shared by the listing query and the (filtered) journal export.
  const filters: JournalFilters = useMemo(
    () => ({
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
    [
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
    ]
  );

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

  function reset() {
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

  return {
    filters,
    facets,
    activeCount,
    hasFilters,
    reset,
    dateFrom,
    dateTo,
    setDateFrom,
    setDateTo,
    search,
    setSearch,
  };
}
