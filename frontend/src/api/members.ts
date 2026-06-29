import type { MembershipStatus, Role } from './auth';
import { api } from './client';

/** A member of the active association (admin view). */
export interface Member {
  user_id: string;
  email: string;
  name: string;
  role: Role;
  status: MembershipStatus;
}

export interface Invitation {
  id: string;
  email: string;
  role: Role;
  created_at: string;
  expires_at: string;
  accepted_at: string | null;
}

export interface InvitationCreated extends Invitation {
  /** Raw token, returned once so a link can be shared in addition to the email. */
  token: string;
}

/** One permission with a human group + label, from the server catalog. */
export interface PermissionInfo {
  value: string;
  group: string;
  label: string;
}

/** A member's permission configuration (T8). */
export interface MemberPermissions {
  user_id: string;
  role: Role;
  /** Admins are a full superset: their permissions are not editable. */
  is_admin: boolean;
  preset_id: string | null;
  /** The built-in role's set (the base used when no preset is assigned). */
  role_permissions: string[];
  /** Current base (role or preset), before per-member overrides. */
  base_permissions: string[];
  /** Per-permission grant (true) / revoke (false) on top of the base. */
  overrides: Record<string, boolean>;
  /** Server-authoritative effective set. */
  effective: string[];
}

export interface SetMemberPermissions {
  preset_id: string | null;
  overrides: Record<string, boolean>;
}

/** A reusable named permission set (custom role). */
export interface Preset {
  id: string;
  nom: string;
  permissions: string[];
}

const base = (associationId: string) => `/asso/${associationId}`;

export const membersApi = {
  list: (associationId: string) => api.get<Member[]>(`${base(associationId)}/members`),
  updateMember: (
    associationId: string,
    userId: string,
    input: { role?: Role; status?: MembershipStatus }
  ) => api.patch<Member>(`${base(associationId)}/members/${userId}`, input),
  removeMember: (associationId: string, userId: string) =>
    api.del<{ message: string }>(`${base(associationId)}/members/${userId}`),

  listInvitations: (associationId: string) =>
    api.get<Invitation[]>(`${base(associationId)}/invitations`),
  createInvitation: (associationId: string, input: { email: string; role: Role }) =>
    api.post<InvitationCreated>(`${base(associationId)}/invitations`, input),
  revokeInvitation: (associationId: string, invitationId: string) =>
    api.del<{ message: string }>(`${base(associationId)}/invitations/${invitationId}`),

  permissionCatalog: (associationId: string) =>
    api.get<PermissionInfo[]>(`${base(associationId)}/permissions/catalog`),
  memberPermissions: (associationId: string, userId: string) =>
    api.get<MemberPermissions>(`${base(associationId)}/members/${userId}/permissions`),
  setMemberPermissions: (associationId: string, userId: string, input: SetMemberPermissions) =>
    api.put<MemberPermissions>(`${base(associationId)}/members/${userId}/permissions`, input),

  listPresets: (associationId: string) =>
    api.get<Preset[]>(`${base(associationId)}/permission-presets`),
  createPreset: (associationId: string, input: { nom: string; permissions: string[] }) =>
    api.post<Preset>(`${base(associationId)}/permission-presets`, input),
  updatePreset: (
    associationId: string,
    presetId: string,
    input: { nom?: string; permissions?: string[] }
  ) => api.patch<Preset>(`${base(associationId)}/permission-presets/${presetId}`, input),
  deletePreset: (associationId: string, presetId: string) =>
    api.del<{ message: string }>(`${base(associationId)}/permission-presets/${presetId}`),
};

/** The caller's context in an association, including effective permissions. */
export interface AssociationContext {
  id: string;
  name: string;
  role: Role;
  permissions: string[];
}

export const associationApi = {
  context: (associationId: string) => api.get<AssociationContext>(`${base(associationId)}`),
};
