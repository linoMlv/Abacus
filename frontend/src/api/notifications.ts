import { api, assoBase as base } from './client';

/** What a notification is about, mirrors the backend `NotificationType`. */
export type NotificationType =
  | 'ecriture_a_valider'
  | 'exercice_a_cloturer'
  | 'budget_depasse'
  | 'evenement_depasse'
  | 'banque_a_rapprocher'
  | 'broadcast';

/** One pending thing awaiting the signed-in member in this association. */
export interface Notification {
  id: string;
  type: NotificationType;
  titre: string;
  message: string | null;
  /** In-app path, relative to the association (e.g. "/journal"). */
  lien: string | null;
  lu_at: string | null;
  created_at: string;
}

export interface NotificationsResponse {
  notifications: Notification[];
  non_lues: number;
}

export const notificationsApi = {
  list: (associationId: string) =>
    api.get<NotificationsResponse>(`${base(associationId)}/notifications`),
  markRead: (associationId: string, notificationId: string) =>
    api.post<Notification>(`${base(associationId)}/notifications/${notificationId}/lecture`, {}),
  markAllRead: (associationId: string) =>
    api.post<{ status: string }>(`${base(associationId)}/notifications/lecture`, {}),
};
