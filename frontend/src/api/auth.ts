import { api } from './client';

export type Role = 'admin' | 'accountant' | 'treasurer' | 'viewer';
export type MembershipStatus = 'active' | 'suspended';

export interface User {
  id: string;
  email: string;
  name: string;
}

/** An association the signed-in user belongs to, with their role in it. */
export interface AssociationSummary {
  id: string;
  name: string;
  role: Role;
  status: MembershipStatus;
}

export interface Session {
  user: User;
  associations: AssociationSummary[];
}

export interface LoginInput {
  email: string;
  password: string;
}

export interface RegisterInput {
  email: string;
  password: string;
  name: string;
}

export const authApi = {
  session: () => api.get<Session>('/auth/session'),
  login: (input: LoginInput) => api.post<Session>('/auth/login', input),
  register: (input: RegisterInput) => api.post<User>('/auth/register', input),
  logout: () => api.post<void>('/auth/logout'),
  createAssociation: (input: { name: string; email: string }) =>
    api.post<AssociationSummary>('/auth/associations', input),
};
