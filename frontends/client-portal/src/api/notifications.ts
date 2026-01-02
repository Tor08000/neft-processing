import type { AuthSession } from "./types";
import { request } from "./http";

const withToken = (user: AuthSession | null): string | undefined => user?.token;

export const subscribePushNotifications = async (user: AuthSession | null, subscription: PushSubscription) => {
  const json = subscription.toJSON();
  if (!json.keys?.p256dh || !json.keys?.auth) {
    throw new Error("missing_push_keys");
  }
  return request(
    "/client/fleet/notifications/push/subscribe",
    {
      method: "POST",
      body: JSON.stringify({
        endpoint: subscription.endpoint,
        p256dh: json.keys.p256dh,
        auth: json.keys.auth,
        user_agent: navigator.userAgent,
      }),
    },
    withToken(user),
  );
};

export const unsubscribePushNotifications = async (user: AuthSession | null, endpoint: string) => {
  return request(
    "/client/fleet/notifications/push/unsubscribe",
    { method: "POST", body: JSON.stringify({ endpoint }) },
    withToken(user),
  );
};
