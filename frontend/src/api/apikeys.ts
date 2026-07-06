import { api } from './client';

/** A machine key for the MCP server, as shown in the admin panel. */
export interface ApiKey {
  id: string;
  name: string;
  /** ``abk_`` + a few chars, to recognise a key (the secret is never re-shown). */
  prefix: string;
  membership_id: string;
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
  /** The member the key acts as (for display). */
  role: string | null;
  member_name: string | null;
  member_email: string | null;
}

/** The one-time creation response: the raw secret, shown exactly once. */
export interface ApiKeyCreated extends ApiKey {
  key: string;
}

const base = (associationId: string) => `/asso/${associationId}`;

export const apiKeysApi = {
  list: (associationId: string) => api.get<ApiKey[]>(`${base(associationId)}/api-keys`),
  create: (associationId: string, input: { name: string; user_id?: string }) =>
    api.post<ApiKeyCreated>(`${base(associationId)}/api-keys`, input),
  revoke: (associationId: string, keyId: string) =>
    api.del<void>(`${base(associationId)}/api-keys/${keyId}`),
};
