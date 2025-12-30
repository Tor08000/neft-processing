import type { AuthSession } from "./types";
import { request } from "./http";

const withToken = (user: AuthSession | null): string | undefined => user?.token;

export const subscribePushNotifications = async (user: AuthSession | null, subscription: PushSubscription) => {
  return request("/notifications/subscribe", { method: "POST", body: JSON.stringify(subscription) }, withToken(user));
};

export const unsubscribePushNotifications = async (user: AuthSession | null, endpoint: string) => {
  return request("/notifications/unsubscribe", { method: "DELETE", body: JSON.stringify({ endpoint }) }, withToken(user));
};
