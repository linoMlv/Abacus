import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Check, Eye, Paperclip, Search, Trash2, X } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
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
import type { Role } from '@/api/auth';
import { apiErrorMessage } from '@/api/client';
import { JustificatifViewer } from '@/components/JustificatifViewer';
import { Alert } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { useActiveAssociation } from '@/hooks/useActiveAssociation';
import { formatAmount, formatBytes, formatDate, formatEUR } from '@/lib/format';
import { canDeleteEntry, canManageAttachment, canValidateEntry } from '@/lib/roles';

const STATUT_LABELS: Record<EcritureStatut, string> = {
  brouillon: 'Brouillon',
  validee: 'Validée',
};

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
  const association = useActiveAssociation();
  const navigate = useNavigate();

  const [statut, setStatut] = useState<EcritureStatut | ''>('');
  const [journalId, setJournalId] = useState('');
  const [compteId, setCompteId] = useState('');
  const [typeOperation, setTypeOperation] = useState<TypeOperation | ''>('');
  const [categorieId, setCategorieId] = useState('');
  const [tiersId, setTiersId] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [search, setSearch] = useState('');
  const q = useDebounced(search);
  const [selectedId, setSelectedId] = useState<string | null>(null);

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

  const ecrituresQuery = useQuery({
    queryKey: [
      'ecritures',
      associationId,
      { statut, journalId, compteId, typeOperation, categorieId, tiersId, dateFrom, dateTo, q },
    ],
    queryFn: () =>
      accountingApi.listEcritures(associationId, {
        statut: statut || undefined,
        journal_id: journalId || undefined,
        compte_id: compteId || undefined,
        type_operation: typeOperation || undefined,
        categorie_id: categorieId || undefined,
        tiers_id: tiersId || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        q: q || undefined,
      }),
  });

  const rows = ecrituresQuery.data ?? [];
  const hasFilters =
    statut !== '' ||
    journalId !== '' ||
    compteId !== '' ||
    typeOperation !== '' ||
    categorieId !== '' ||
    tiersId !== '' ||
    dateFrom !== '' ||
    dateTo !== '' ||
    q !== '';

  function resetFilters() {
    setStatut('');
    setJournalId('');
    setCompteId('');
    setTypeOperation('');
    setCategorieId('');
    setTiersId('');
    setDateFrom('');
    setDateTo('');
    setSearch('');
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold tracking-tight text-ink">Journal</h2>
          <p className="mt-1 text-sm text-muted">
            Toutes les écritures de l’exercice, les plus récentes d’abord.
          </p>
        </div>
        <Button variant="accent" onClick={() => navigate(`/asso/${associationId}/saisie`)}>
          Nouvelle opération
        </Button>
      </div>

      <Card className="p-3">
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative min-w-50 flex-1">
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
          <Select
            aria-label="Filtrer par statut"
            className="w-44"
            value={statut}
            onChange={(e) => setStatut(e.target.value as EcritureStatut | '')}
          >
            <option value="">Tous les statuts</option>
            <option value="brouillon">Brouillons</option>
            <option value="validee">Validées</option>
          </Select>
          <Select
            aria-label="Filtrer par journal"
            className="w-44"
            value={journalId}
            onChange={(e) => setJournalId(e.target.value)}
          >
            <option value="">Tous les journaux</option>
            {(journauxQuery.data ?? []).map((j) => (
              <option key={j.id} value={j.id}>
                {j.code} — {j.libelle}
              </option>
            ))}
          </Select>
          <Select
            aria-label="Filtrer par compte de trésorerie"
            className="w-48"
            value={compteId}
            onChange={(e) => setCompteId(e.target.value)}
          >
            <option value="">Tous les comptes</option>
            {(tresorerieQuery.data ?? []).map((c) => (
              <option key={c.id} value={c.id}>
                {c.libelle}
              </option>
            ))}
          </Select>
          <Select
            aria-label="Filtrer par type d’opération"
            className="w-40"
            value={typeOperation}
            onChange={(e) => setTypeOperation(e.target.value as TypeOperation | '')}
          >
            <option value="">Tous les types</option>
            {(['recette', 'depense', 'virement'] as const).map((t) => (
              <option key={t} value={t}>
                {TYPE_OPERATION_LABELS[t]}
              </option>
            ))}
          </Select>
          <Select
            aria-label="Filtrer par catégorie"
            className="w-48"
            value={categorieId}
            onChange={(e) => setCategorieId(e.target.value)}
          >
            <option value="">Toutes les catégories</option>
            {(categoriesQuery.data ?? []).map((c) => (
              <option key={c.id} value={c.id}>
                {c.libelle}
              </option>
            ))}
          </Select>
          <Select
            aria-label="Filtrer par tiers"
            className="w-44"
            value={tiersId}
            onChange={(e) => setTiersId(e.target.value)}
          >
            <option value="">Tous les tiers</option>
            {(tiersQuery.data ?? []).map((t) => (
              <option key={t.id} value={t.id}>
                {t.nom}
              </option>
            ))}
          </Select>
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-muted">Du</span>
            <Input
              type="date"
              aria-label="Date de début"
              className="w-40"
              value={dateFrom}
              max={dateTo || undefined}
              onChange={(e) => setDateFrom(e.target.value)}
            />
            <span className="text-xs text-muted">au</span>
            <Input
              type="date"
              aria-label="Date de fin"
              className="w-40"
              value={dateTo}
              min={dateFrom || undefined}
              onChange={(e) => setDateTo(e.target.value)}
            />
          </div>
          {hasFilters && (
            <button
              type="button"
              onClick={resetFilters}
              className="ml-auto inline-flex items-center gap-1 text-sm font-medium text-muted hover:text-ink"
            >
              <X className="h-4 w-4" aria-hidden />
              Réinitialiser
            </button>
          )}
        </div>
      </Card>

      {ecrituresQuery.isError ? (
        <Alert>Impossible de charger les écritures.</Alert>
      ) : rows.length === 0 ? (
        <EmptyState associationId={associationId} filtered={hasFilters} />
      ) : (
        <JournalTable rows={rows} onSelect={setSelectedId} />
      )}

      {selectedId && (
        <EcritureDrawer
          associationId={associationId}
          ecritureId={selectedId}
          role={association?.role}
          onClose={() => setSelectedId(null)}
        />
      )}
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
      <table className="w-full text-sm">
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
    </Card>
  );
}

/** Justificatifs of an entry: list, preview, upload (PDF/image, 5 Mo), delete. */
function JustificatifsSection({
  associationId,
  ecritureId,
  role,
}: {
  associationId: string;
  ecritureId: string;
  role?: Role;
}) {
  const queryClient = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const [localError, setLocalError] = useState<string | null>(null);
  const [viewing, setViewing] = useState<Justificatif | null>(null);
  const canManage = role ? canManageAttachment(role) : false;

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
  role,
  onClose,
}: {
  associationId: string;
  ecritureId: string;
  role?: Role;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
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
  const canValidate = role ? canValidateEntry(role) : false;
  const canDelete = role ? canDeleteEntry(role) : false;
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

              <JustificatifsSection
                associationId={associationId}
                ecritureId={ecritureId}
                role={role}
              />
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
