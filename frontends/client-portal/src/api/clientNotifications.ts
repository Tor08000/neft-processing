import type { AuthSession } from "./types";
import { request } from "./http";

const withToken = (user: AuthSession | null): string | undefined => user?.token;

export type ClientNotification = {
  id: string;
  type: string;
  severity: "INFO" | "WARNING" | "CRITICAL";
  title: string;
  body: string;
  link?: string | null;
  created_at: string;
  read_at?: string | null;
};

export type ClientNotificationsResponse = {
  items: ClientNotification[];
  next_cursor?: string | null;
};

export type ClientNotificationsUnreadCount = {
  count: number;
};

export const listClientNotifications = async (
  user: AuthSession | null,
  params: { unreadOnly?: boolean; limit?: number; cursor?: string | null } = {},
): Promise<ClientNotificationsResponse> => {
  const search = new URLSearchParams();
  if (typeof params.unreadOnly === "boolean") {
    search.set("unread_only", String(params.unreadOnly));
  }
  if (params.limit) {
    search.set("limit", String(params.limit));
  }
  if (params.cursor) {
    search.set("cursor", params.cursor);
  }
  const suffix = search.toString();
  return request(
    `/client/notifications${suffix ? `?${suffix}` : ""}`,
    { method: "GET" },
    withToken(user),
  );
};

export const markClientNotificationRead = async (user: AuthSession | null, id: string): Promise<ClientNotification> => {
  return request(`/client/notifications/${id}/read`, { method: "POST" }, withToken(user));
};

export const markAllClientNotificationsRead = async (user: AuthSession | null, unreadOnly = true): Promise<{ updated: number }> => {
  const search = new URLSearchParams({ unread_only: String(unreadOnly) });
  return request(`/client/notifications/read-all?${search.toString()}`, { method: "POST" }, withToken(user));
};

export const getClientNotificationsUnreadCount = async (user: AuthSession | null): Promise<ClientNotificationsUnreadCount> => {
  return request("/client/notifications/unread-count", { method: "GET" }, withToken(user));
};
