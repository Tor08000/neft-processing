import { useCallback, useEffect, useState } from "react";
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
  disableChannel,
  listChannels,
} from "../api/fleetNotifications";
import type { FleetNotificationChannel } from "../types/fleetNotifications";
import { canAdminFleetNotifications } from "../utils/fleetPermissions";
import { formatDateTime } from "../utils/format";

const generateSecret = () => {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID().replaceAll("-", "");
  }
  return Math.random().toString(36).slice(2, 18);
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

  useEffect(() => {
    if (!canAdmin) return;
    void loadChannels();
  }, [canAdmin, loadChannels]);

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

  if (!canAdmin) {
    return <AppForbiddenState message={t("fleetNotifications.errors.adminOnly")} />;
  }

  if (loading) {
    return (
      <div className="page">
        <div className="page-header">
          <h1>{t("fleetNotifications.channels.title")}</h1>
        </div>
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
          <h1>{t("fleetNotifications.channels.title")}</h1>
        </div>
        <AppErrorState message={error} onRetry={() => void loadChannels()} />
      </div>
    );
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1>{t("fleetNotifications.channels.title")}</h1>
        <div className="actions">
          <button type="button" className="primary" onClick={() => { resetForm(); setShowCreateModal(true); }}>
            {t("fleetNotifications.channels.create")}
          </button>
          <button type="button" className="secondary" onClick={() => void loadChannels()}>
            {t("actions.refresh")}
          </button>
        </div>
      </div>
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
              </div>
            </div>
          ))}
        </div>
      )}
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
