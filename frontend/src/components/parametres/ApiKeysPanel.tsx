import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Copy, KeyRound, Plus } from 'lucide-react';
import { useState } from 'react';

import { apiKeysApi, type ApiKeyCreated } from '@/api/apikeys';
import { apiErrorMessage } from '@/api/client';
import { membersApi } from '@/api/members';
import { Alert } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { ROLE_LABELS } from '@/lib/roles';

function formatWhen(value: string | null): string {
  if (!value) return 'jamais';
  return new Date(value).toLocaleDateString('fr-FR', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

/**
 * Manage API keys for the MCP server (admin, apikey:manage). A key acts as a
 * chosen member and inherits their permissions, so binding a viewer yields a
 * read-only assistant and a treasurer an entry-capable one. The secret is shown
 * once, at creation; afterwards only a prefix identifies it.
 */
export function ApiKeysPanel({ associationId }: { associationId: string }) {
  const queryClient = useQueryClient();
  const [name, setName] = useState('');
  const [userId, setUserId] = useState('');
  const [created, setCreated] = useState<ApiKeyCreated | null>(null);
  const [copied, setCopied] = useState(false);

  const keysQuery = useQuery({
    queryKey: ['api-keys', associationId],
    queryFn: () => apiKeysApi.list(associationId),
  });
  const membersQuery = useQuery({
    queryKey: ['members', associationId],
    queryFn: () => membersApi.list(associationId),
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['api-keys', associationId] });

  const create = useMutation({
    mutationFn: () =>
      apiKeysApi.create(associationId, {
        name: name.trim(),
        user_id: userId || undefined,
      }),
    onSuccess: (key: ApiKeyCreated) => {
      setName('');
      setUserId('');
      setCreated(key);
      setCopied(false);
      invalidate();
    },
  });
  const revoke = useMutation({
    mutationFn: (id: string) => apiKeysApi.revoke(associationId, id),
    onSuccess: invalidate,
  });

  const mcpUrl = `${window.location.origin}/mcp`;
  const copyKey = async () => {
    if (!created) return;
    await navigator.clipboard.writeText(created.key);
    setCopied(true);
  };

  const members = membersQuery.data ?? [];
  const keys = keysQuery.data ?? [];

  return (
    <div className="space-y-8">
      <section className="space-y-3">
        <div>
          <h3 className="text-sm font-semibold text-ink-soft">Clés API / MCP</h3>
          <p className="text-sm text-muted">
            Une clé permet à un assistant (via le serveur MCP) de consulter votre comptabilité — et,
            si le membre choisi le permet, d’enregistrer des écritures en brouillon. Elle agit avec
            les droits de ce membre.
          </p>
        </div>

        <Card className="space-y-4 p-4">
          <form
            className="flex flex-wrap items-end gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              if (name.trim()) create.mutate();
            }}
          >
            <div className="min-w-[12rem] flex-1">
              <label htmlFor="key-name" className="mb-1 block text-xs font-medium text-ink-soft">
                Nom de la clé
              </label>
              <Input
                id="key-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Assistant Claude"
                required
              />
            </div>
            <div>
              <label htmlFor="key-member" className="mb-1 block text-xs font-medium text-ink-soft">
                Agit en tant que
              </label>
              <Select
                id="key-member"
                className="w-56"
                value={userId}
                onChange={(e) => setUserId(e.target.value)}
              >
                <option value="">Moi</option>
                {members.map((m) => (
                  <option key={m.user_id} value={m.user_id}>
                    {m.name} — {ROLE_LABELS[m.role]}
                  </option>
                ))}
              </Select>
            </div>
            <Button type="submit" disabled={create.isPending || !name.trim()}>
              <Plus className="h-4 w-4" aria-hidden />
              Créer une clé
            </Button>
          </form>

          {create.isError && <Alert>{apiErrorMessage(create, 'Création impossible.')}</Alert>}

          {created && (
            <div className="space-y-2 rounded-lg border border-accent/30 bg-accent-soft px-3.5 py-3">
              <p className="text-sm font-medium text-ink">
                Clé créée. Copiez-la maintenant : elle ne sera plus affichée.
              </p>
              <div className="flex items-center gap-2">
                <code className="min-w-0 flex-1 truncate rounded bg-surface px-2 py-1 text-xs text-ink">
                  {created.key}
                </code>
                <Button type="button" variant="outline" size="sm" onClick={copyKey}>
                  <Copy className="h-3.5 w-3.5" aria-hidden />
                  {copied ? 'Copié' : 'Copier'}
                </Button>
              </div>
              <p className="text-xs text-muted">
                Configurez votre client MCP avec l’URL <code className="text-ink">{mcpUrl}</code> et
                l’en-tête <code className="text-ink">X-API-Key</code> égal à cette clé.
              </p>
            </div>
          )}
        </Card>
      </section>

      <section className="space-y-3">
        <h3 className="text-sm font-semibold text-ink-soft">Clés existantes</h3>
        {keysQuery.isLoading ? (
          <p className="text-sm text-muted">Chargement…</p>
        ) : keysQuery.isError ? (
          <Alert>Impossible de charger les clés.</Alert>
        ) : keys.length === 0 ? (
          <Card className="flex items-center gap-3 p-6 text-sm text-muted">
            <KeyRound className="h-5 w-5" aria-hidden />
            Aucune clé pour l’instant.
          </Card>
        ) : (
          <Card className="p-0">
            <ul className="divide-y divide-hairline">
              {keys.map((k) => (
                <li key={k.id} className="flex items-center gap-3 px-4 py-3">
                  <div className="min-w-0 flex-1">
                    <p className="flex items-center gap-2 text-sm text-ink">
                      <span className="truncate font-medium">{k.name}</span>
                      <code className="text-xs text-muted">{k.prefix}…</code>
                      {k.revoked_at && (
                        <span className="rounded bg-depense-soft px-1.5 py-0.5 text-xs text-depense">
                          Révoquée
                        </span>
                      )}
                    </p>
                    <p className="text-xs text-muted">
                      {k.member_name ?? '—'}
                      {k.role
                        ? ` (${ROLE_LABELS[k.role as keyof typeof ROLE_LABELS] ?? k.role})`
                        : ''}{' '}
                      · dernière utilisation : {formatWhen(k.last_used_at)}
                    </p>
                  </div>
                  {!k.revoked_at && (
                    <Button
                      variant="ghost"
                      size="sm"
                      disabled={revoke.isPending}
                      onClick={() => revoke.mutate(k.id)}
                    >
                      Révoquer
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          </Card>
        )}
      </section>
    </div>
  );
}
