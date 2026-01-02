import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { useI18n } from "../i18n";
import { ConfirmActionModal } from "../components/ConfirmActionModal";
import { Toast } from "../components/Toast/Toast";
import { useToast } from "../components/Toast/useToast";
import { AppErrorState, AppForbiddenState } from "../components/states";
import { FleetUnavailableState } from "../components/FleetUnavailableState";
import { ApiError } from "../api/http";
import {
  createChannel,
  createTelegramLink,
  disableChannel,
  disableTelegramBinding,
  listChannels,
  listTelegramBindings,
  testChannel,
  subscribePush,
  unsubscribePush,
  getPushStatus,
  sendTestPush,
} from "../api/fleetNotifications";
import { listGroups } from "../api/fleet";
import type {
  FleetNotificationChannel,
  FleetPushSubscription,
  FleetTelegramBinding,
  FleetTelegramLink,
} from "../types/fleetNotifications";
import type { FleetGroup } from "../types/fleet";
import { canAdminFleetNotifications } from "../utils/fleetPermissions";
import { formatDateTime } from "../utils/format";
import { PolicyCenterTabs } from "../components/PolicyCenterTabs";

const generateSecret = () => {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID().replaceAll("-", "");
  }
  return Math.random().toString(36).slice(2, 18);
};

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

export function FleetNotificationChannelsPage() {
  const { user } = useAuth();
  const { t } = useI18n();
  const { toast, showToast } = useToast();
  const [channels, setChannels] = useState<FleetNotificationChannel[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [unavailable, setUnavailable] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [channelType, setChannelType] = useState("WEBHOOK");
  const [target, setTarget] = useState("");
  const [secret, setSecret] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [disableTarget, setDisableTarget] = useState<FleetNotificationChannel | null>(null);
  const [pushSubscription, setPushSubscription] = useState<PushSubscription | null>(null);
  const [pushStatus, setPushStatus] = useState<FleetPushSubscription | null>(null);
  const [pushLoading, setPushLoading] = useState(false);
  const [pushError, setPushError] = useState<string | null>(null);
  const [telegramBindings, setTelegramBindings] = useState<FleetTelegramBinding[]>([]);
  const [telegramLink, setTelegramLink] = useState<FleetTelegramLink | null>(null);
  const [telegramScope, setTelegramScope] = useState("client");
  const [telegramGroupId, setTelegramGroupId] = useState("");
  const [telegramGroups, setTelegramGroups] = useState<FleetGroup[]>([]);
  const [telegramLoading, setTelegramLoading] = useState(false);
  const [telegramError, setTelegramError] = useState<string | null>(null);
  const [now, setNow] = useState(Date.now());
  const vapidKey = import.meta.env.VITE_PUSH_PUBLIC_KEY;
  const supportsPush = "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
  const pushAvailable = supportsPush && Boolean(vapidKey);
  const groupNameById = useMemo(() => {
    return new Map(telegramGroups.map((group) => [group.id, group.name]));
  }, [telegramGroups]);

  const canAdmin = canAdminFleetNotifications(user);

  const loadChannels = useCallback(async () => {
    if (!user?.token) return;
    setLoading(true);
    setError(null);
    setUnavailable(false);
    try {
      const response = await listChannels(user.token);
      if (response.unavailable) {
        setUnavailable(true);
        return;
      }
      setChannels(response.items);
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        setError(t("fleetNotifications.errors.noPermission"));
        return;
      }
      setError(err instanceof Error ? err.message : t("fleetNotifications.errors.loadFailed"));
    } finally {
      setLoading(false);
    }
  }, [t, user?.token]);

  const loadTelegram = useCallback(async () => {
    if (!user?.token) return;
    setTelegramLoading(true);
    setTelegramError(null);
    try {
      const [bindingsResponse, groupsResponse] = await Promise.all([
        listTelegramBindings(user.token),
        listGroups(user.token),
      ]);
      if (bindingsResponse.unavailable || groupsResponse.unavailable) {
        setUnavailable(true);
        return;
      }
      setTelegramBindings(bindingsResponse.items);
      setTelegramGroups(groupsResponse.items ?? []);
    } catch (err) {
      setTelegramError(err instanceof Error ? err.message : t("fleetNotifications.errors.actionFailed"));
    } finally {
      setTelegramLoading(false);
    }
  }, [t, user?.token]);

  useEffect(() => {
    if (!canAdmin) return;
    void loadChannels();
    void loadTelegram();
  }, [canAdmin, loadChannels, loadTelegram]);

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 30000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (!user?.token || !supportsPush) return;
    navigator.serviceWorker.ready
      .then((registration) => registration.pushManager.getSubscription())
      .then(async (subscription) => {
        setPushSubscription(subscription);
        if (!subscription) {
          setPushStatus(null);
          return;
        }
        const statusResponse = await getPushStatus(user.token, subscription.endpoint);
        if (statusResponse.unavailable) {
          setUnavailable(true);
          return;
        }
        setPushStatus(statusResponse.item ?? null);
      })
      .catch(() => setPushStatus(null));
  }, [supportsPush, user?.token]);

  useEffect(() => {
    setTelegramLink(null);
  }, [telegramScope, telegramGroupId]);

  const resetForm = () => {
    setChannelType("WEBHOOK");
    setTarget("");
    setSecret("");
    setFormError(null);
  };

  const validate = () => {
    if (!target.trim()) {
      return t("fleetNotifications.channels.validationTarget");
    }
    if (channelType === "WEBHOOK") {
      try {
        new URL(target.trim());
      } catch {
        return t("fleetNotifications.channels.validationUrl");
      }
    }
    if (channelType === "EMAIL" && !target.includes("@")) {
      return t("fleetNotifications.channels.validationEmail");
    }
    return null;
  };

  const handleCreate = async () => {
    if (!user?.token) return;
    const validationError = validate();
    if (validationError) {
      setFormError(validationError);
      return;
    }
    setFormError(null);
    const secretValue = channelType === "WEBHOOK" ? secret.trim() || generateSecret() : undefined;
    try {
      const response = await createChannel(user.token, {
        channel_type: channelType,
        target: target.trim(),
        secret: secretValue,
      });
      if (response.unavailable) {
        setUnavailable(true);
        return;
      }
      if (response.item) {
        setChannels((prev) => [response.item!, ...prev]);
      }
      showToast({ kind: "success", text: t("fleetNotifications.channels.created") });
      setShowCreateModal(false);
      resetForm();
    } catch (err) {
      showToast({ kind: "error", text: err instanceof Error ? err.message : t("fleetNotifications.errors.actionFailed") });
    }
  };

  const handleDisable = async () => {
    if (!user?.token || !disableTarget) return;
    try {
      const response = await disableChannel(user.token, disableTarget.id);
      if (response.unavailable) {
        setUnavailable(true);
        return;
      }
      const updated = response.item ?? { ...disableTarget, status: "DISABLED" };
      setChannels((prev) => prev.map((item) => (item.id === disableTarget.id ? { ...item, ...updated } : item)));
      showToast({ kind: "success", text: t("fleetNotifications.channels.disabled") });
      setDisableTarget(null);
    } catch (err) {
      showToast({ kind: "error", text: err instanceof Error ? err.message : t("fleetNotifications.errors.actionFailed") });
    }
  };

  const handleTestChannel = async (channelId: string) => {
    if (!user?.token) return;
    try {
      const response = await testChannel(user.token, channelId);
      if (response.unavailable) {
        setUnavailable(true);
        return;
      }
      showToast({ kind: "success", text: t("fleetNotifications.channels.testSent") });
    } catch (err) {
      showToast({ kind: "error", text: err instanceof Error ? err.message : t("fleetNotifications.errors.actionFailed") });
    }
  };

  const handleEnablePush = async () => {
    if (!user?.token || !pushAvailable) {
      setPushError(t("fleetNotifications.push.notSupported"));
      return;
    }
    if (!vapidKey) {
      setPushError(t("fleetNotifications.push.notSupported"));
      return;
    }
    setPushLoading(true);
    setPushError(null);
    try {
      const permission = await Notification.requestPermission();
      if (permission !== "granted") {
        setPushError(t("fleetNotifications.push.permissionDenied"));
        return;
      }
      const registration = await navigator.serviceWorker.ready;
      let subscription = await registration.pushManager.getSubscription();
      if (!subscription) {
        subscription = await registration.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToUint8Array(vapidKey),
        });
      }
      const json = subscription.toJSON();
      if (!json.keys?.p256dh || !json.keys?.auth) {
        throw new Error("missing_keys");
      }
      const response = await subscribePush(user.token, {
        endpoint: subscription.endpoint,
        p256dh: json.keys.p256dh,
        auth: json.keys.auth,
        user_agent: navigator.userAgent,
      });
      if (response.unavailable) {
        setUnavailable(true);
        return;
      }
      setPushSubscription(subscription);
      setPushStatus(response.item ?? null);
      showToast({ kind: "success", text: t("fleetNotifications.push.enabled") });
    } catch (err) {
      setPushError(err instanceof Error ? err.message : t("fleetNotifications.errors.actionFailed"));
    } finally {
      setPushLoading(false);
    }
  };

  const handleDisablePush = async () => {
    if (!user?.token || !pushSubscription) return;
    setPushLoading(true);
    setPushError(null);
    try {
      await pushSubscription.unsubscribe();
      const response = await unsubscribePush(user.token, pushSubscription.endpoint);
      if (response.unavailable) {
        setUnavailable(true);
        return;
      }
      setPushSubscription(null);
      setPushStatus(response.item ?? null);
      showToast({ kind: "success", text: t("fleetNotifications.push.disabled") });
    } catch (err) {
      setPushError(err instanceof Error ? err.message : t("fleetNotifications.errors.actionFailed"));
    } finally {
      setPushLoading(false);
    }
  };

  const handleTestPush = async () => {
    if (!user?.token) return;
    try {
      const response = await sendTestPush(user.token);
      if (response.unavailable) {
        setUnavailable(true);
        return;
      }
      showToast({ kind: "success", text: t("fleetNotifications.push.testSent") });
    } catch (err) {
      showToast({ kind: "error", text: err instanceof Error ? err.message : t("fleetNotifications.errors.actionFailed") });
    }
  };

  const handleCreateTelegramLink = async () => {
    if (!user?.token) return;
    if (telegramScope === "group" && !telegramGroupId) {
      setTelegramError(t("fleetNotifications.telegram.missingGroup"));
      return;
    }
    setTelegramLoading(true);
    setTelegramError(null);
    try {
      const response = await createTelegramLink(user.token, {
        scope_type: telegramScope,
        scope_id: telegramScope === "group" ? telegramGroupId : null,
      });
      if (response.unavailable) {
        setUnavailable(true);
        return;
      }
      if (response.item) {
        setTelegramLink(response.item);
        showToast({ kind: "success", text: t("fleetNotifications.telegram.linkCreated") });
      }
    } catch (err) {
      setTelegramError(err instanceof Error ? err.message : t("fleetNotifications.errors.actionFailed"));
    } finally {
      setTelegramLoading(false);
    }
  };

  const handleDisableTelegramBinding = async (binding: FleetTelegramBinding) => {
    if (!user?.token) return;
    try {
      const response = await disableTelegramBinding(user.token, binding.id);
      if (response.unavailable) {
        setUnavailable(true);
        return;
      }
      const updated = response.item ?? { ...binding, status: "DISABLED" };
      setTelegramBindings((prev) => prev.map((item) => (item.id === binding.id ? { ...item, ...updated } : item)));
      showToast({ kind: "success", text: t("fleetNotifications.telegram.bindingDisabled") });
    } catch (err) {
      showToast({ kind: "error", text: err instanceof Error ? err.message : t("fleetNotifications.errors.actionFailed") });
    }
  };

  if (!canAdmin) {
    return <AppForbiddenState message={t("fleetNotifications.errors.adminOnly")} />;
  }

  if (loading) {
    return (
      <div className="page">
        <div className="page-header">
          <h1>{t("policyCenter.channelsTitle")}</h1>
        </div>
        <PolicyCenterTabs />
        <div className="card state">{t("common.loading")}</div>
      </div>
    );
  }

  if (unavailable) {
    return <FleetUnavailableState />;
  }

  if (error) {
    return (
      <div className="page">
        <div className="page-header">
          <h1>{t("policyCenter.channelsTitle")}</h1>
        </div>
        <PolicyCenterTabs />
        <AppErrorState message={error} onRetry={() => void loadChannels()} />
      </div>
    );
  }

  const telegramExpiresInSeconds = telegramLink
    ? Math.max(0, Math.floor((Date.parse(telegramLink.expires_at) - now) / 1000))
    : null;
  const telegramExpiresInMinutes =
    telegramExpiresInSeconds !== null ? Math.ceil(telegramExpiresInSeconds / 60) : null;

  return (
    <div className="page">
      <div className="page-header">
        <h1>{t("policyCenter.channelsTitle")}</h1>
        <div className="actions">
          <button type="button" className="primary" onClick={() => { resetForm(); setShowCreateModal(true); }}>
            {t("fleetNotifications.channels.create")}
          </button>
          <button type="button" className="secondary" onClick={() => void loadChannels()}>
            {t("actions.refresh")}
          </button>
        </div>
      </div>
      <PolicyCenterTabs />
      {!channels.length ? (
        <div className="card state">
          <h2>{t("fleetNotifications.channels.emptyTitle")}</h2>
          <div className="muted">{t("fleetNotifications.channels.emptyDescription")}</div>
        </div>
      ) : (
        <div className="channel-list">
          {channels.map((channel) => (
            <div key={channel.id} className="card channel-card">
              <div className="channel-card__header">
                <div>
                  <span className="badge badge-info">
                    {channel.channel_type === "WEBHOOK"
                      ? t("fleetNotifications.channels.webhook")
                      : channel.channel_type === "EMAIL"
                        ? t("fleetNotifications.channels.email")
                        : channel.channel_type === "PUSH"
                          ? t("fleetNotifications.channels.push")
                          : channel.channel_type === "TELEGRAM"
                            ? t("fleetNotifications.channels.telegram")
                            : channel.channel_type ?? t("common.notAvailable")}
                  </span>
                  <div className="channel-card__target">{channel.target ?? t("common.notAvailable")}</div>
                </div>
                <span className={channel.status === "DISABLED" ? "badge badge-muted" : "badge badge-success"}>
                  {channel.status === "DISABLED"
                    ? t("fleetNotifications.channels.statusDisabled")
                    : t("fleetNotifications.channels.statusActive")}
                </span>
              </div>
              <div className="channel-card__meta">
                {channel.created_at ? (
                  <span>{t("fleetNotifications.channels.createdAt", { value: formatDateTime(channel.created_at) })}</span>
                ) : null}
              </div>
              <div className="actions">
                <button
                  type="button"
                  className="ghost"
                  onClick={() => setDisableTarget(channel)}
                  disabled={channel.status === "DISABLED"}
                >
                  {t("fleetNotifications.channels.disable")}
                </button>
                <button
                  type="button"
                  className="ghost"
                  onClick={() => void handleTestChannel(channel.id)}
                  disabled={channel.status === "DISABLED"}
                >
                  {t("fleetNotifications.channels.sendTest")}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
      <div className="card telegram-card">
        <div className="channel-card__header">
          <div>
            <span className="badge badge-info">{t("fleetNotifications.telegram.title")}</span>
            <div className="channel-card__target">{t("fleetNotifications.telegram.subtitle")}</div>
          </div>
          <span className={telegramBindings.some((binding) => binding.status === "ACTIVE") ? "badge badge-success" : "badge badge-muted"}>
            {telegramBindings.some((binding) => binding.status === "ACTIVE")
              ? t("fleetNotifications.telegram.statusActive")
              : t("fleetNotifications.telegram.statusInactive")}
          </span>
        </div>
        <div className="channel-card__meta">
          <span className="muted">{t("fleetNotifications.telegram.description")}</span>
          {telegramLoading ? <span className="muted">{t("common.loading")}</span> : null}
        </div>
        {telegramError ? <div className="error-text">{telegramError}</div> : null}
        <div className="form-grid">
          <label className="form-field">
            <span>{t("fleetNotifications.telegram.scopeType")}</span>
            <select value={telegramScope} onChange={(event) => setTelegramScope(event.target.value)}>
              <option value="client">{t("fleetNotifications.telegram.scopeClient")}</option>
              <option value="group">{t("fleetNotifications.telegram.scopeGroup")}</option>
            </select>
          </label>
          {telegramScope === "group" ? (
            <label className="form-field">
              <span>{t("fleetNotifications.telegram.group")}</span>
              <select value={telegramGroupId} onChange={(event) => setTelegramGroupId(event.target.value)}>
                <option value="">{t("fleetNotifications.telegram.groupSelect")}</option>
                {telegramGroups.map((group) => (
                  <option key={group.id} value={group.id}>
                    {group.name}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
        </div>
        <div className="actions">
          <button type="button" className="primary" onClick={() => void handleCreateTelegramLink()} disabled={telegramLoading}>
            {t("fleetNotifications.telegram.connect")}
          </button>
        </div>
        {telegramLink ? (
          <div className="channel-card__headers">
            <span className="muted">{t("fleetNotifications.telegram.linkReady")}</span>
            <div className="actions">
              <a className="ghost" href={telegramLink.deep_link} target="_blank" rel="noreferrer">
                {t("fleetNotifications.telegram.openTelegram")}
              </a>
              {telegramExpiresInMinutes !== null ? (
                <span className="muted">{t("fleetNotifications.telegram.expiresIn", { minutes: telegramExpiresInMinutes })}</span>
              ) : null}
            </div>
          </div>
        ) : null}
      </div>
      {telegramBindings.length ? (
        <div className="channel-list">
          {telegramBindings.map((binding) => (
            <div key={binding.id} className="card channel-card">
              <div className="channel-card__header">
                <div>
                  <span className="badge badge-info">{t("fleetNotifications.telegram.chat")}</span>
                  <div className="channel-card__target">{binding.chat_title ?? t("fleetNotifications.telegram.chatFallback")}</div>
                </div>
                <span className={binding.status === "DISABLED" ? "badge badge-muted" : "badge badge-success"}>
                  {binding.status === "DISABLED"
                    ? t("fleetNotifications.telegram.statusDisabled")
                    : t("fleetNotifications.telegram.statusEnabled")}
                </span>
              </div>
              <div className="channel-card__meta">
                <span>
                  {binding.scope_type === "client"
                    ? t("fleetNotifications.telegram.scopeClient")
                    : t("fleetNotifications.telegram.scopeGroupLabel", {
                        name: binding.scope_id ? groupNameById.get(binding.scope_id) ?? binding.scope_id : t("fleetNotifications.telegram.scopeGroup"),
                      })}
                </span>
                {binding.created_at ? (
                  <span>{t("fleetNotifications.telegram.createdAt", { value: formatDateTime(binding.created_at) })}</span>
                ) : null}
              </div>
              <div className="actions">
                <button
                  type="button"
                  className="ghost"
                  onClick={() => void handleDisableTelegramBinding(binding)}
                  disabled={binding.status === "DISABLED"}
                >
                  {t("fleetNotifications.telegram.disable")}
                </button>
              </div>
            </div>
          ))}
        </div>
      ) : null}
      <div className="card push-card">
        <div className="channel-card__header">
          <div>
            <span className="badge badge-info">{t("fleetNotifications.channels.push")}</span>
            <div className="channel-card__target">{t("fleetNotifications.push.deviceLabel")}</div>
          </div>
          <span className={pushSubscription ? "badge badge-success" : "badge badge-muted"}>
            {pushSubscription ? t("fleetNotifications.push.enabledStatus") : t("fleetNotifications.push.disabledStatus")}
          </span>
        </div>
        <div className="channel-card__meta">
          {pushStatus?.last_sent_at ? (
            <span>{t("fleetNotifications.push.lastSent", { value: formatDateTime(pushStatus.last_sent_at) })}</span>
          ) : (
            <span className="muted">{t("fleetNotifications.push.neverSent")}</span>
          )}
          {!pushAvailable ? <span className="muted">{t("fleetNotifications.push.notSupported")}</span> : null}
        </div>
        {pushError ? <div className="error-text">{pushError}</div> : null}
        <div className="actions">
          <button
            type="button"
            className="ghost"
            onClick={() => void handleEnablePush()}
            disabled={!pushAvailable || pushLoading}
          >
            {t("fleetNotifications.push.enable")}
          </button>
          <button
            type="button"
            className="ghost"
            onClick={() => void handleDisablePush()}
            disabled={!pushSubscription || pushLoading}
          >
            {t("fleetNotifications.push.disable")}
          </button>
          <button
            type="button"
            className="ghost"
            onClick={() => void handleTestPush()}
            disabled={!pushSubscription || pushLoading}
          >
            {t("fleetNotifications.push.sendTest")}
          </button>
        </div>
      </div>
      {showCreateModal ? (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal-card">
            <h2>{t("fleetNotifications.channels.createTitle")}</h2>
            <div className="form-grid">
              <label className="form-field">
                <span>{t("fleetNotifications.channels.type")}</span>
                <select value={channelType} onChange={(event) => setChannelType(event.target.value)}>
                  <option value="WEBHOOK">{t("fleetNotifications.channels.webhook")}</option>
                  <option value="EMAIL">{t("fleetNotifications.channels.email")}</option>
                </select>
              </label>
              <label className="form-field">
                <span>{channelType === "WEBHOOK" ? t("fleetNotifications.channels.url") : t("fleetNotifications.channels.email")}</span>
                <input value={target} onChange={(event) => setTarget(event.target.value)} placeholder={channelType === "WEBHOOK" ? "https://..." : "user@example.com"} />
              </label>
              {channelType === "WEBHOOK" ? (
                <>
                  <label className="form-field">
                    <span>{t("fleetNotifications.channels.secret")}</span>
                    <input value={secret} onChange={(event) => setSecret(event.target.value)} placeholder={t("fleetNotifications.channels.secretPlaceholder")} />
                  </label>
                  <div className="channel-card__headers">
                    <span className="muted">{t("fleetNotifications.channels.headersTitle")}</span>
                    <ul>
                      <li>X-NEFT-Signature</li>
                      <li>X-NEFT-Signature-Timestamp</li>
                      <li>X-NEFT-Event-Id</li>
                      <li>X-NEFT-Event-Type</li>
                    </ul>
                  </div>
                </>
              ) : null}
            </div>
            {formError ? <div className="error-text">{formError}</div> : null}
            <div className="actions">
              <button type="button" className="ghost" onClick={() => setShowCreateModal(false)}>
                {t("actions.comeBackLater")}
              </button>
              <button type="button" className="primary" onClick={() => void handleCreate()}>
                {t("fleetNotifications.channels.submit")}
              </button>
            </div>
          </div>
        </div>
      ) : null}
      <ConfirmActionModal
        isOpen={!!disableTarget}
        title={t("fleetNotifications.channels.disableTitle")}
        description={t("fleetNotifications.channels.disableDescription")}
        confirmLabel={t("fleetNotifications.channels.disableConfirm")}
        cancelLabel={t("actions.comeBackLater")}
        onConfirm={() => void handleDisable()}
        onCancel={() => setDisableTarget(null)}
      />
      <Toast toast={toast} />
    </div>
  );
}
