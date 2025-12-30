import { useEffect, useMemo, useState } from "react";
import { subscribePushNotifications, unsubscribePushNotifications } from "../api/notifications";
import { useAuth } from "../auth/AuthContext";
import { useI18n } from "../i18n";
import { isPwaMode } from "./mode";

const getPermission = () => ("Notification" in window ? Notification.permission : "denied");

const urlBase64ToUint8Array = (base64String: string) => {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; i += 1) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
};

type PushState = "idle" | "prompt" | "denied" | "subscribed" | "subscribing";

export function PwaNotificationsPrompt() {
  const { user } = useAuth();
  const { t } = useI18n();
  const [state, setState] = useState<PushState>("idle");

  const supportsPush = useMemo(
    () => isPwaMode && "serviceWorker" in navigator && "PushManager" in window && "Notification" in window,
    [],
  );

  const vapidKey = import.meta.env.VITE_PUSH_PUBLIC_KEY;

  const ensureSubscription = async () => {
    if (!user || !supportsPush || !vapidKey) {
      return;
    }
    setState("subscribing");
    const registration = await navigator.serviceWorker.ready;
    let subscription = await registration.pushManager.getSubscription();
    if (!subscription) {
      subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(vapidKey),
      });
    }
    await subscribePushNotifications(user, subscription);
    setState("subscribed");
  };

  useEffect(() => {
    if (!supportsPush) {
      return;
    }
    const permission = getPermission();
    if (permission === "granted") {
      ensureSubscription().catch(() => setState("idle"));
      return;
    }
    if (permission === "denied") {
      setState("denied");
      navigator.serviceWorker.ready
        .then((registration) => registration.pushManager.getSubscription())
        .then((subscription) => {
          if (!subscription || !user) return;
          return unsubscribePushNotifications(user, subscription.endpoint);
        })
        .catch(() => undefined);
      return;
    }
    setState("prompt");
  }, [supportsPush, user, vapidKey]);

  const handleRequest = async () => {
    if (!supportsPush) {
      return;
    }
    const permission = await Notification.requestPermission();
    if (permission !== "granted") {
      setState(permission === "denied" ? "denied" : "prompt");
      return;
    }
    await ensureSubscription();
  };

  if (!supportsPush || !user || !vapidKey) {
    return null;
  }

  if (state !== "prompt") {
    return null;
  }

  return (
    <div className="card pwa-banner">
      <div>
        <strong>{t("pwa.notifications.title")}</strong>
        <p className="muted">{t("pwa.notifications.description")}</p>
      </div>
      <button type="button" className="primary" onClick={() => void handleRequest()}>
        {t("pwa.notifications.enable")}
      </button>
    </div>
  );
}
