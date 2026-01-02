import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { useI18n } from "../i18n";
import { Table } from "../components/common/Table";
import type { Column } from "../components/common/Table";
import { ConfirmActionModal } from "../components/ConfirmActionModal";
import { Toast } from "../components/Toast/Toast";
import { useToast } from "../components/Toast/useToast";
import { AppForbiddenState, AppErrorState } from "../components/states";
import { FleetUnavailableState } from "../components/FleetUnavailableState";
import { ApiError } from "../api/http";
import {
  listPolicies,
  createPolicy,
  disablePolicy,
  listChannels,
} from "../api/fleetNotifications";
import { listCards, listGroups } from "../api/fleet";
import type { FleetNotificationChannel, FleetNotificationPolicy } from "../types/fleetNotifications";
import type { FleetCard, FleetGroup } from "../types/fleet";
import { canAdminFleetNotifications } from "../utils/fleetPermissions";

const policyChannelsFromIds = (
  policy: FleetNotificationPolicy,
  channels: FleetNotificationChannel[],
): FleetNotificationChannel[] => {
  if (policy.channels?.length) return policy.channels;
  if (policy.channel_types?.length) {
    return policy.channel_types.map((type) => ({ id: type, channel_type: type }));
  }
  if (!policy.channel_ids?.length) return [];
  return channels.filter((channel) => policy.channel_ids?.includes(channel.id));
};

export function FleetNotificationPoliciesPage() {
  const { user } = useAuth();
  const { t } = useI18n();
  const { toast, showToast } = useToast();
  const [policies, setPolicies] = useState<FleetNotificationPolicy[]>([]);
  const [channels, setChannels] = useState<FleetNotificationChannel[]>([]);
  const [cards, setCards] = useState<FleetCard[]>([]);
  const [groups, setGroups] = useState<FleetGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [unavailable, setUnavailable] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [scopeType, setScopeType] = useState("CLIENT");
  const [scopeId, setScopeId] = useState("");
  const [eventType, setEventType] = useState("");
  const [severityMin, setSeverityMin] = useState("");
  const [cooldown, setCooldown] = useState("300");
  const [selectedChannels, setSelectedChannels] = useState<string[]>([]);
  const [autoAction, setAutoAction] = useState("NONE");
  const [formError, setFormError] = useState<string | null>(null);
  const [disableTarget, setDisableTarget] = useState<FleetNotificationPolicy | null>(null);

  const canAdmin = canAdminFleetNotifications(user);

  const loadPolicies = useCallback(async () => {
    if (!user?.token) return;
    setLoading(true);
    setError(null);
    setUnavailable(false);
    try {
      const [policiesResponse, channelsResponse, cardsResponse, groupsResponse] = await Promise.all([
        listPolicies(user.token),
        listChannels(user.token),
        listCards(user.token),
        listGroups(user.token),
      ]);
      if (
        policiesResponse.unavailable ||
        channelsResponse.unavailable ||
        cardsResponse.unavailable ||
        groupsResponse.unavailable
      ) {
        setUnavailable(true);
        return;
      }
      setPolicies(policiesResponse.items);
      setChannels(channelsResponse.items);
      setCards(cardsResponse.items);
      setGroups(groupsResponse.items);
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
    void loadPolicies();
  }, [canAdmin, loadPolicies]);

  const columns: Column<FleetNotificationPolicy>[] = useMemo(
    () => [
      {
        key: "scope",
        title: t("fleetNotifications.policies.scope"),
        render: (policy) => {
          if (policy.scope_type === "CLIENT") return t("fleetNotifications.policies.scopeClient");
          if (policy.scope_type === "GROUP") return policy.group_name ?? t("fleetNotifications.policies.scopeGroupFallback");
          if (policy.scope_type === "CARD") return policy.card_alias ?? t("fleetNotifications.policies.scopeCardFallback");
          return t("common.notAvailable");
        },
      },
      {
        key: "eventType",
        title: t("fleetNotifications.policies.eventType"),
        render: (policy) => {
          if (policy.event_type === "LIMIT_BREACH") return t("fleetNotifications.alerts.typeLimit");
          if (policy.event_type === "ANOMALY") return t("fleetNotifications.alerts.typeAnomaly");
          if (policy.event_type === "INGEST_FAILED") return t("fleetNotifications.alerts.typeIngest");
          return policy.event_type ?? t("common.notAvailable");
        },
      },
      {
        key: "severity",
        title: t("fleetNotifications.policies.severityMin"),
        render: (policy) => <span className="badge badge-muted">{policy.severity_min ?? "—"}</span>,
      },
      {
        key: "channels",
        title: t("fleetNotifications.policies.channels"),
        render: (policy) => (
          <div className="channel-tags">
            {policyChannelsFromIds(policy, channels).map((channel) => (
              <span key={channel.id} className="badge badge-info">
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
            ))}
          </div>
        ),
      },
      {
        key: "cooldown",
        title: t("fleetNotifications.policies.cooldown"),
        render: (policy) => t("fleetNotifications.policies.cooldownValue", { value: policy.cooldown_seconds ?? 0 }),
      },
      {
        key: "autoAction",
        title: t("fleetNotifications.policies.autoAction"),
        render: (policy) =>
          policy.auto_action === "AUTO_BLOCK"
            ? t("fleetNotifications.policies.autoBlock")
            : t("fleetNotifications.policies.autoNone"),
      },
      {
        key: "status",
        title: t("fleetNotifications.policies.status"),
        render: (policy) => (
          <span className={policy.status === "DISABLED" ? "badge badge-muted" : "badge badge-success"}>
            {policy.status === "DISABLED"
              ? t("fleetNotifications.policies.statusDisabled")
              : t("fleetNotifications.policies.statusActive")}
          </span>
        ),
      },
      {
        key: "actions",
        title: t("fleetNotifications.policies.actions"),
        render: (policy) => (
          <div className="actions">
            <button
              type="button"
              className="ghost"
              onClick={() => setDisableTarget(policy)}
              disabled={policy.status === "DISABLED"}
            >
              {t("fleetNotifications.policies.disable")}
            </button>
          </div>
        ),
      },
    ],
    [channels, t],
  );

  const resetForm = () => {
    setScopeType("CLIENT");
    setScopeId("");
    setEventType("");
    setSeverityMin("");
    setCooldown("300");
    setSelectedChannels([]);
    setAutoAction("NONE");
    setFormError(null);
  };

  const handleCreate = async () => {
    if (!user?.token) return;
    if (!eventType || !severityMin) {
      setFormError(t("fleetNotifications.policies.validationRequired"));
      return;
    }
    if ((scopeType === "GROUP" || scopeType === "CARD") && !scopeId) {
      setFormError(t("fleetNotifications.policies.validationScope"));
      return;
    }
    if (!selectedChannels.length) {
      setFormError(t("fleetNotifications.policies.validationChannels"));
      return;
    }
    const cooldownValue = Number(cooldown);
    if (!Number.isFinite(cooldownValue) || cooldownValue <= 0) {
      setFormError(t("fleetNotifications.policies.validationCooldown"));
      return;
    }
    if (autoAction === "AUTO_BLOCK" && !(eventType === "LIMIT_BREACH" && severityMin === "CRITICAL")) {
      setFormError(t("fleetNotifications.policies.validationAutoBlock"));
      return;
    }
    setFormError(null);
    try {
      const response = await createPolicy(user.token, {
        scope_type: scopeType,
        scope_id: scopeType === "CLIENT" ? undefined : scopeId,
        event_type: eventType,
        severity_min: severityMin,
        channel_ids: selectedChannels,
        cooldown_seconds: cooldownValue,
        auto_action: autoAction,
      });
      if (response.unavailable) {
        setUnavailable(true);
        return;
      }
      if (response.item) {
        setPolicies((prev) => [response.item!, ...prev]);
      }
      showToast({ kind: "success", text: t("fleetNotifications.policies.created") });
      setShowCreateModal(false);
      resetForm();
    } catch (err) {
      showToast({ kind: "error", text: err instanceof Error ? err.message : t("fleetNotifications.errors.actionFailed") });
    }
  };

  const handleDisable = async () => {
    if (!user?.token || !disableTarget) return;
    try {
      const response = await disablePolicy(user.token, disableTarget.id);
      if (response.unavailable) {
        setUnavailable(true);
        return;
      }
      const updated = response.item ?? { ...disableTarget, status: "DISABLED" };
      setPolicies((prev) => prev.map((policy) => (policy.id === disableTarget.id ? { ...policy, ...updated } : policy)));
      showToast({ kind: "success", text: t("fleetNotifications.policies.disabled") });
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
          <h1>{t("fleetNotifications.policies.title")}</h1>
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
          <h1>{t("fleetNotifications.policies.title")}</h1>
        </div>
        <AppErrorState message={error} onRetry={() => void loadPolicies()} />
      </div>
    );
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1>{t("fleetNotifications.policies.title")}</h1>
        <div className="actions">
          <button type="button" className="primary" onClick={() => { resetForm(); setShowCreateModal(true); }}>
            {t("fleetNotifications.policies.create")}
          </button>
          <button type="button" className="secondary" onClick={() => void loadPolicies()}>
            {t("actions.refresh")}
          </button>
        </div>
      </div>
      <Table
        columns={columns}
        data={policies}
        emptyState={{
          title: t("fleetNotifications.policies.emptyTitle"),
          description: t("fleetNotifications.policies.emptyDescription"),
        }}
      />
      {showCreateModal ? (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal-card">
            <h2>{t("fleetNotifications.policies.createTitle")}</h2>
            <div className="form-grid">
              <label className="form-field">
                <span>{t("fleetNotifications.policies.scopeType")}</span>
                <select
                  value={scopeType}
                  onChange={(event) => {
                    setScopeType(event.target.value);
                    setScopeId("");
                  }}
                >
                  <option value="CLIENT">{t("fleetNotifications.policies.scopeClient")}</option>
                  <option value="GROUP">{t("fleetNotifications.policies.scopeGroup")}</option>
                  <option value="CARD">{t("fleetNotifications.policies.scopeCard")}</option>
                </select>
              </label>
              {scopeType === "GROUP" ? (
                <label className="form-field">
                  <span>{t("fleetNotifications.policies.group")}</span>
                  <select value={scopeId} onChange={(event) => setScopeId(event.target.value)}>
                    <option value="">{t("fleetNotifications.policies.scopeSelect")}</option>
                    {groups.map((group) => (
                      <option key={group.id} value={group.id}>
                        {group.name}
                      </option>
                    ))}
                  </select>
                </label>
              ) : null}
              {scopeType === "CARD" ? (
                <label className="form-field">
                  <span>{t("fleetNotifications.policies.card")}</span>
                  <select value={scopeId} onChange={(event) => setScopeId(event.target.value)}>
                    <option value="">{t("fleetNotifications.policies.scopeSelect")}</option>
                    {cards.map((card) => (
                      <option key={card.id} value={card.id}>
                        {card.card_alias ?? t("fleetNotifications.policies.cardFallback")}
                      </option>
                    ))}
                  </select>
                </label>
              ) : null}
              <label className="form-field">
                <span>{t("fleetNotifications.policies.eventType")}</span>
                <select value={eventType} onChange={(event) => setEventType(event.target.value)}>
                  <option value="">{t("fleetNotifications.policies.eventSelect")}</option>
                  <option value="LIMIT_BREACH">{t("fleetNotifications.alerts.typeLimit")}</option>
                  <option value="ANOMALY">{t("fleetNotifications.alerts.typeAnomaly")}</option>
                  <option value="INGEST_FAILED">{t("fleetNotifications.alerts.typeIngest")}</option>
                </select>
              </label>
              <label className="form-field">
                <span>{t("fleetNotifications.policies.severityMin")}</span>
                <select value={severityMin} onChange={(event) => setSeverityMin(event.target.value)}>
                  <option value="">{t("fleetNotifications.policies.severitySelect")}</option>
                  <option value="LOW">LOW</option>
                  <option value="MEDIUM">MEDIUM</option>
                  <option value="HIGH">HIGH</option>
                  <option value="CRITICAL">CRITICAL</option>
                </select>
              </label>
              <label className="form-field">
                <span>{t("fleetNotifications.policies.channels")}</span>
                <div className="checkbox-grid">
                  {channels.map((channel) => (
                    <label key={channel.id} className="checkbox-row">
                      <input
                        type="checkbox"
                        checked={selectedChannels.includes(channel.id)}
                        onChange={(event) => {
                          setSelectedChannels((prev) =>
                            event.target.checked ? [...prev, channel.id] : prev.filter((id) => id !== channel.id),
                          );
                        }}
                      />
                      <span>
                        {channel.channel_type === "WEBHOOK"
                          ? t("fleetNotifications.channels.webhook")
                          : channel.channel_type === "EMAIL"
                            ? t("fleetNotifications.channels.email")
                            : channel.channel_type === "PUSH"
                              ? t("fleetNotifications.channels.push")
                              : channel.channel_type === "TELEGRAM"
                                ? t("fleetNotifications.channels.telegram")
                                : channel.channel_type ?? t("common.notAvailable")}
                        {" · "}
                        {channel.target ?? t("common.notAvailable")}
                      </span>
                    </label>
                  ))}
                </div>
              </label>
              <label className="form-field">
                <span>{t("fleetNotifications.policies.cooldown")}</span>
                <input value={cooldown} onChange={(event) => setCooldown(event.target.value)} type="number" min={60} />
              </label>
              <label className="form-field">
                <span>{t("fleetNotifications.policies.autoAction")}</span>
                <select value={autoAction} onChange={(event) => setAutoAction(event.target.value)}>
                  <option value="NONE">{t("fleetNotifications.policies.autoNone")}</option>
                  <option value="AUTO_BLOCK">{t("fleetNotifications.policies.autoBlock")}</option>
                </select>
              </label>
            </div>
            {autoAction === "AUTO_BLOCK" ? (
              <div className="warning-text">{t("fleetNotifications.policies.autoBlockWarning")}</div>
            ) : null}
            {formError ? <div className="error-text">{formError}</div> : null}
            <div className="actions">
              <button type="button" className="ghost" onClick={() => setShowCreateModal(false)}>
                {t("actions.comeBackLater")}
              </button>
              <button type="button" className="primary" onClick={() => void handleCreate()}>
                {t("fleetNotifications.policies.submit")}
              </button>
            </div>
          </div>
        </div>
      ) : null}
      <ConfirmActionModal
        isOpen={!!disableTarget}
        title={t("fleetNotifications.policies.disableTitle")}
        description={t("fleetNotifications.policies.disableDescription")}
        confirmLabel={t("fleetNotifications.policies.disableConfirm")}
        cancelLabel={t("actions.comeBackLater")}
        onConfirm={() => void handleDisable()}
        onCancel={() => setDisableTarget(null)}
      />
      <Toast toast={toast} />
    </div>
  );
}
