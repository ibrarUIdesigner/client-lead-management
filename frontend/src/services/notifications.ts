import { api } from "./api";
import type {
  NotificationItem,
  NotificationListResponse,
  NotificationPreferences,
  NotificationPreferencesUpdate,
  PushPublicKeyResponse,
  UnreadCountResponse,
} from "../types/notification";

export async function fetchNotifications(params?: {
  is_read?: boolean;
  type?: string;
  limit?: number;
  offset?: number;
}): Promise<NotificationListResponse> {
  const { data } = await api.get<NotificationListResponse>("/notifications", {
    params,
  });
  return data;
}

export async function fetchUnreadCount(): Promise<number> {
  const { data } = await api.get<UnreadCountResponse>("/notifications/unread-count");
  return data.unread_count;
}

export async function markNotificationRead(id: string): Promise<NotificationItem> {
  const { data } = await api.post<NotificationItem>(`/notifications/${id}/read`);
  return data;
}

export async function markAllNotificationsRead(): Promise<{ updated: number }> {
  const { data } = await api.post<{ updated: number }>("/notifications/read-all");
  return data;
}

export async function deleteNotification(id: string): Promise<void> {
  await api.delete(`/notifications/${id}`);
}

export async function fetchNotificationPreferences(): Promise<NotificationPreferences> {
  const { data } = await api.get<NotificationPreferences>("/notifications/preferences");
  return data;
}

export async function updateNotificationPreferences(
  update: NotificationPreferencesUpdate,
): Promise<NotificationPreferences> {
  const { data } = await api.put<NotificationPreferences>("/notifications/preferences", update);
  return data;
}

export async function fetchPushPublicKey(): Promise<PushPublicKeyResponse> {
  const { data } = await api.get<PushPublicKeyResponse>("/push/public-key");
  return data;
}

export async function subscribeToPush(subscription: {
  endpoint: string;
  keys: { p256dh: string; auth: string };
  device_name?: string;
}): Promise<{ status: string }> {
  const { data } = await api.post<{ status: string }>("/push/subscribe", subscription);
  return data;
}

export async function unsubscribeFromPush(endpoint: string): Promise<{ status: string }> {
  const { data } = await api.delete<{ status: string }>("/push/subscribe", {
    data: { endpoint },
  });
  return data;
}

export async function sendTestPush(): Promise<{ status: string; notification_id?: string }> {
  const { data } = await api.post<{ status: string; notification_id?: string }>("/push/test");
  return data;
}
