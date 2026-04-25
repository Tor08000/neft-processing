import { useEffect, useMemo, useRef, useState } from "react";
import { LinkIcon } from "../components/icons";
import { useAuth } from "../auth/AuthContext";
import { EmptyState } from "../components/EmptyState";
import { ErrorState, ForbiddenState, LoadingState } from "../components/states";
import { StatusBadge } from "../components/StatusBadge";
import { CopyButton } from "../components/CopyButton";
import { SupportRequestModal } from "../components/SupportRequestModal";
import { defaultWebhookEvents } from "../constants/webhookEvents";
import {
  createWebhookEndpoint,
  createWebhookSubscription,
  deleteWebhookSubscription,
  fetchWebhookAlerts,
  fetchWebhookDeliveries,
  fetchWebhookDeliveryDetail,
  fetchWebhookEndpoints,
  fetchWebhookSla,
  fetchWebhookSubscriptions,
  pauseWebhookEndpoint,
  replayWebhookDeliveries,
  resumeWebhookEndpoint,
  retryWebhookDelivery,
  rotateWebhookSecret,
  sendWebhookTest,
  updateWebhookEndpointStatus,
  updateWebhookSubscription,
} from "../api/webhooks";
import { ApiError } from "../api/http";
import type {
  WebhookAlert,
  WebhookDelivery,
  WebhookDeliveryDetail,
  WebhookEndpoint,
  WebhookSlaStatus,
  WebhookSubscription,
  WebhookTestResult,
} from "../types/webhooks";
import { useTranslation } from "react-i18next";
import i18n from "../i18n";

type ApiErrorState = {
  message: string;
  status?: number;
  correlationId?: string | null;
};

const normalizeError = (err: unknown, fallback: string): ApiErrorState => {
  if (err instanceof ApiError) {
    return { message: err.message, status: err.status, correlationId: err.correlationId };
  }
  return { message: fallback };
};

const formatErrorDescription = (error: ApiErrorState): string => {
  const parts = [error.message];
  if (error.status) {
    parts.push(i18n.t("errors.errorCode", { code: error.status }));
  }
  return parts.join(" · ");
};

const formatDateTime = (value: string | null | undefined) => {
  if (!value) return i18n.t("common.notAvailable");
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("ru-RU");
};

const stringifyFilters = (filters: Record<string, unknown> | null | undefined) => {
  if (!filters) return "";
  try {
    return JSON.stringify(filters, null, 2);
  } catch (err) {
    return "";
  }
};

const parseFilters = (raw: string): Record<string, unknown> | null => {
  if (!raw.trim()) return null;
  try {
    return JSON.parse(raw) as Record<string, unknown>;
  } catch (err) {
    return null;
  }
};

export function IntegrationsPage() {
  const { user, hasPartnerRole } = useAuth();
  const { t } = useTranslation();
  const isOwner = Boolean(user?.roles.includes("PARTNER_OWNER"));
  const deliveriesRef = useRef<HTMLDivElement | null>(null);

  const [endpoints, setEndpoints] = useState<WebhookEndpoint[]>([]);
  const [endpointLoading, setEndpointLoading] = useState(true);
  const [endpointError, setEndpointError] = useState<ApiErrorState | null>(null);
  const [selectedEndpointId, setSelectedEndpointId] = useState<string | null>(null);

  const [subscriptions, setSubscriptions] = useState<WebhookSubscription[]>([]);
  const [subscriptionLoading, setSubscriptionLoading] = useState(false);
  const [subscriptionError, setSubscriptionError] = useState<ApiErrorState | null>(null);

  const [deliveries, setDeliveries] = useState<WebhookDelivery[]>([]);
  const [deliveryLoading, setDeliveryLoading] = useState(false);
  const [deliveryError, setDeliveryError] = useState<ApiErrorState | null>(null);
  const [deliveryTab, setDeliveryTab] = useState<"history" | "dlq">("history");
  const [deliveryFilters, setDeliveryFilters] = useState({
    status: "",
    eventType: "",
    eventId: "",
    from: "",
    to: "",
    limit: 20,
  });

  const [deliveryDetail, setDeliveryDetail] = useState<WebhookDeliveryDetail | null>(null);
  const [deliveryDetailLoading, setDeliveryDetailLoading] = useState(false);
  const [deliveryDetailError, setDeliveryDetailError] = useState<ApiErrorState | null>(null);
  const [isSupportOpen, setIsSupportOpen] = useState(false);
  const [isDeliveryDetailOpen, setIsDeliveryDetailOpen] = useState(false);

  const [slaStatus, setSlaStatus] = useState<WebhookSlaStatus | null>(null);
  const [slaLoading, setSlaLoading] = useState(false);
  const [slaError, setSlaError] = useState<ApiErrorState | null>(null);
  const [alerts, setAlerts] = useState<WebhookAlert[]>([]);
  const [alertsLoading, setAlertsLoading] = useState(false);
  const [alertsError, setAlertsError] = useState<ApiErrorState | null>(null);

  const [eventTypes, setEventTypes] = useState<string[]>(defaultWebhookEvents);

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState({
    url: "",
    signingAlgo: "HMAC_SHA256",
    enabled: true,
  });
  const [createError, setCreateError] = useState<ApiErrorState | null>(null);
  const [createdEndpointInfo, setCreatedEndpointInfo] = useState<{
    endpointId: string;
    secret: string;
    correlationId: string | null;
  } | null>(null);

  const [rotatedSecretInfo, setRotatedSecretInfo] = useState<{
    endpointId: string;
    secret: string;
    correlationId: string | null;
  } | null>(null);

  const [testPingResult, setTestPingResult] = useState<{
    endpointId: string;
    result: WebhookTestResult;
    correlationId: string | null;
  } | null>(null);

  const [subscriptionFiltersDraft, setSubscriptionFiltersDraft] = useState<Record<string, string>>({});
  const [isReplayOpen, setIsReplayOpen] = useState(false);
  const [replayForm, setReplayForm] = useState({
    from: "",
    to: "",
    eventTypes: "",
    onlyFailed: true,
  });
  const [replayResult, setReplayResult] = useState<{
    replayId: string;
    scheduled: number;
    correlationId: string | null;
  } | null>(null);
  const [replayError, setReplayError] = useState<ApiErrorState | null>(null);

  const selectedEndpoint = useMemo(
    () => endpoints.find((endpoint) => endpoint.id === selectedEndpointId) ?? null,
    [endpoints, selectedEndpointId],
  );

  const catalogEventTypes = useMemo(() => {
    const values = new Set(eventTypes);
    subscriptions.forEach((subscription) => values.add(subscription.event_type));
    return Array.from(values);
  }, [eventTypes, subscriptions]);

  useEffect(() => {
    if (!user) return;
    setEndpointLoading(true);
    setEndpointError(null);
    fetchWebhookEndpoints(user.token, user.partnerId ?? "")
      .then((data) => {
        setEndpoints(data);
        if (!selectedEndpointId && data.length > 0) {
          setSelectedEndpointId(data[0].id);
        }
      })
      .catch((err) => setEndpointError(normalizeError(err, t("integrationsPage.errors.loadEndpoints"))))
      .finally(() => setEndpointLoading(false));
  }, [user, selectedEndpointId]);

  useEffect(() => {
    if (!selectedEndpointId || !user) return;
    setSubscriptionLoading(true);
    setSubscriptionError(null);
    fetchWebhookSubscriptions(user.token, selectedEndpointId)
      .then((data) => {
        setSubscriptions(data);
        const drafts: Record<string, string> = {};
        data.forEach((subscription) => {
          drafts[subscription.event_type] = stringifyFilters(subscription.filters);
        });
        setSubscriptionFiltersDraft((prev) => ({ ...prev, ...drafts }));
      })
      .catch((err) => setSubscriptionError(normalizeError(err, t("integrationsPage.errors.loadSubscriptions"))))
      .finally(() => setSubscriptionLoading(false));
  }, [selectedEndpointId, user]);

  useEffect(() => {
    if (!selectedEndpointId || !user) return;
    setDeliveryLoading(true);
    setDeliveryError(null);
    const status = deliveryTab === "dlq" ? "DEAD" : deliveryFilters.status || undefined;
    fetchWebhookDeliveries(user.token, {
      endpointId: selectedEndpointId,
      status,
      from: deliveryFilters.from || undefined,
      to: deliveryFilters.to || undefined,
      limit: deliveryFilters.limit,
      eventType: deliveryFilters.eventType || undefined,
      eventId: deliveryFilters.eventId || undefined,
    })
      .then((data) => setDeliveries(data))
      .catch((err) => setDeliveryError(normalizeError(err, t("integrationsPage.errors.loadDeliveries"))))
      .finally(() => setDeliveryLoading(false));
  }, [deliveryFilters, deliveryTab, selectedEndpointId, user]);

  useEffect(() => {
    if (!selectedEndpointId || !user) return;
    setSlaLoading(true);
    setSlaError(null);
    fetchWebhookSla(user.token, selectedEndpointId)
      .then((data) => setSlaStatus(data))
      .catch((err) => setSlaError(normalizeError(err, t("integrationsPage.errors.loadSla"))))
      .finally(() => setSlaLoading(false));
  }, [selectedEndpointId, user]);

  useEffect(() => {
    if (!selectedEndpointId || !user) return;
    setAlertsLoading(true);
    setAlertsError(null);
    fetchWebhookAlerts(user.token, selectedEndpointId)
      .then((data) => setAlerts(data))
      .catch((err) => setAlertsError(normalizeError(err, t("integrationsPage.errors.loadAlerts"))))
      .finally(() => setAlertsLoading(false));
  }, [selectedEndpointId, user]);

  const handleCreateEndpoint = async () => {
    if (!user) return;
    setCreateError(null);
    if (!/^https?:\/\//.test(createForm.url)) {
      setCreateError({ message: t("integrationsPage.errors.invalidUrl") });
      return;
    }
    try {
      const response = await createWebhookEndpoint(user.token, {
        owner_type: "PARTNER",
        owner_id: user.partnerId ?? "",
        url: createForm.url,
        signing_algo: createForm.signingAlgo as "HMAC_SHA256",
        enabled: createForm.enabled,
      });
      const endpointId =
        response.data.endpoint?.id ?? response.data.endpoint_id ?? response.data.id ?? "—";
      setCreatedEndpointInfo({ endpointId, secret: response.data.secret, correlationId: response.correlationId });
      const refreshed = await fetchWebhookEndpoints(user.token, user.partnerId ?? "");
      setEndpoints(refreshed);
      if (!selectedEndpointId && refreshed.length > 0) {
        setSelectedEndpointId(refreshed[0].id);
      }
    } catch (err) {
      setCreateError(normalizeError(err, t("integrationsPage.errors.createEndpointFailed")));
    }
  };

  const handleToggleEndpoint = async (endpoint: WebhookEndpoint) => {
    if (!user) return;
    const nextStatus = endpoint.status === "ACTIVE" ? "DISABLED" : "ACTIVE";
    const confirmation = window.confirm(
      nextStatus === "DISABLED"
        ? t("integrationsPage.confirmations.disableEndpoint")
        : t("integrationsPage.confirmations.enableEndpoint"),
    );
    if (!confirmation) return;
    try {
      await updateWebhookEndpointStatus(user.token, endpoint.id, nextStatus);
      setEndpoints((prev) =>
        prev.map((item) => (item.id === endpoint.id ? { ...item, status: nextStatus } : item)),
      );
    } catch (err) {
      setEndpointError(normalizeError(err, t("integrationsPage.errors.updateEndpointFailed")));
    }
  };

  const handleRotateSecret = async (endpoint: WebhookEndpoint) => {
    if (!user) return;
    const confirmation = window.confirm(t("integrationsPage.confirmations.rotateSecret"));
    if (!confirmation) return;
    try {
      const response = await rotateWebhookSecret(user.token, endpoint.id);
      setRotatedSecretInfo({
        endpointId: endpoint.id,
        secret: response.data.secret,
        correlationId: response.correlationId,
      });
    } catch (err) {
      setEndpointError(normalizeError(err, t("integrationsPage.errors.rotateSecretFailed")));
    }
  };

  const handleTestPing = async (endpoint: WebhookEndpoint) => {
    if (!user) return;
    try {
      const response = await sendWebhookTest(user.token, endpoint.id, "test.ping");
      setTestPingResult({ endpointId: endpoint.id, result: response.data, correlationId: response.correlationId });
    } catch (err) {
      setEndpointError(normalizeError(err, t("integrationsPage.errors.sendTestFailed")));
    }
  };

  const handleSelectEndpoint = (endpointId: string) => {
    setSelectedEndpointId(endpointId);
    deliveriesRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const handleToggleSubscription = async (eventType: string, enabled: boolean) => {
    if (!user || !selectedEndpointId) return;
    const existing = subscriptions.find((subscription) => subscription.event_type === eventType);
    try {
      if (existing) {
        const updated = await updateWebhookSubscription(user.token, existing.id, enabled);
        setSubscriptions((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      } else {
        const rawFilters = subscriptionFiltersDraft[eventType] ?? "";
        const filters = parseFilters(rawFilters);
        if (rawFilters.trim() && !filters) {
          setSubscriptionError({ message: t("integrationsPage.errors.invalidFilters") });
          return;
        }
        const created = await createWebhookSubscription(user.token, selectedEndpointId, eventType, enabled, filters);
        setSubscriptions((prev) => [...prev, created]);
      }
    } catch (err) {
      setSubscriptionError(normalizeError(err, t("integrationsPage.errors.updateSubscriptionFailed")));
    }
  };

  const handleDeleteSubscription = async (subscription: WebhookSubscription) => {
    if (!user) return;
    const confirmation = window.confirm(t("integrationsPage.confirmations.deleteSubscription"));
    if (!confirmation) return;
    try {
      await deleteWebhookSubscription(user.token, subscription.id);
      setSubscriptions((prev) => prev.filter((item) => item.id !== subscription.id));
    } catch (err) {
      setSubscriptionError(normalizeError(err, t("integrationsPage.errors.deleteSubscriptionFailed")));
    }
  };

  const handleOpenDeliveryDetail = async (delivery: WebhookDelivery) => {
    if (!user) return;
    setDeliveryDetailLoading(true);
    setDeliveryDetailError(null);
    setIsDeliveryDetailOpen(true);
    setDeliveryDetail(null);
    try {
      const detail = await fetchWebhookDeliveryDetail(user.token, delivery.id);
      setDeliveryDetail(detail);
    } catch (err) {
      setDeliveryDetailError(normalizeError(err, t("integrationsPage.errors.loadDeliveryDetailFailed")));
    } finally {
      setDeliveryDetailLoading(false);
    }
  };

  const handleRetryDelivery = async (delivery: WebhookDelivery) => {
    if (!user) return;
    const confirmation = window.confirm(t("integrationsPage.confirmations.retryDelivery"));
    if (!confirmation) return;
    try {
      await retryWebhookDelivery(user.token, delivery.id);
      const refreshed = await fetchWebhookDeliveries(user.token, {
        endpointId: delivery.endpoint_id,
        status: deliveryTab === "dlq" ? "DEAD" : deliveryFilters.status || undefined,
        from: deliveryFilters.from || undefined,
        to: deliveryFilters.to || undefined,
        limit: deliveryFilters.limit,
        eventType: deliveryFilters.eventType || undefined,
        eventId: deliveryFilters.eventId || undefined,
      });
      setDeliveries(refreshed);
    } catch (err) {
      setDeliveryError(normalizeError(err, t("integrationsPage.errors.retryDeliveryFailed")));
    }
  };

  const handleBulkRetry = async () => {
    if (!user) return;
    const confirmation = window.confirm(t("integrationsPage.confirmations.retryDeadDeliveries"));
    if (!confirmation) return;
    const deadItems = deliveries.filter((item) => item.status === "DEAD");
    try {
      await Promise.all(deadItems.map((item) => retryWebhookDelivery(user.token, item.id)));
      const refreshed = await fetchWebhookDeliveries(user.token, {
        endpointId: selectedEndpointId ?? "",
        status: "DEAD",
        limit: deliveryFilters.limit,
      });
      setDeliveries(refreshed);
    } catch (err) {
      setDeliveryError(normalizeError(err, t("integrationsPage.errors.retryDeadFailed")));
    }
  };

  const handlePauseEndpoint = async (endpoint: WebhookEndpoint) => {
    if (!user) return;
    const confirmation = window.confirm(t("integrationsPage.confirmations.pauseEndpoint"));
    if (!confirmation) return;
    try {
      const updated = await pauseWebhookEndpoint(user.token, endpoint.id, "partner_requested");
      setEndpoints((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
    } catch (err) {
      setEndpointError(normalizeError(err, t("integrationsPage.errors.pauseEndpointFailed")));
    }
  };

  const handleResumeEndpoint = async (endpoint: WebhookEndpoint) => {
    if (!user) return;
    const confirmation = window.confirm(t("integrationsPage.confirmations.resumeEndpoint"));
    if (!confirmation) return;
    try {
      const updated = await resumeWebhookEndpoint(user.token, endpoint.id);
      setEndpoints((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
    } catch (err) {
      setEndpointError(normalizeError(err, t("integrationsPage.errors.resumeEndpointFailed")));
    }
  };

  const handleReplay = async () => {
    if (!user || !selectedEndpoint) return;
    setReplayError(null);
    const eventTypes = replayForm.eventTypes
      .split(",")
      .map((value) => value.trim())
      .filter(Boolean);
    const fromIso = replayForm.from ? new Date(replayForm.from).toISOString() : "";
    const toIso = replayForm.to ? new Date(replayForm.to).toISOString() : "";
    try {
      const response = await replayWebhookDeliveries(user.token, selectedEndpoint.id, {
        from: fromIso,
        to: toIso,
        event_types: eventTypes.length > 0 ? eventTypes : undefined,
        only_failed: replayForm.onlyFailed,
      });
      setReplayResult({
        replayId: response.data.replay_id,
        scheduled: response.data.scheduled_deliveries,
        correlationId: response.correlationId,
      });
    } catch (err) {
      setReplayError(normalizeError(err, t("integrationsPage.errors.replayFailed")));
    }
  };

  const renderAlertMessage = (alert: WebhookAlert) => {
    switch (alert.type) {
      case "SLA_BREACH":
        return t("integrationsPage.alerts.slaBreach");
      case "DELIVERY_FAILURE":
        return t("integrationsPage.alerts.deliveryFailure");
      case "PAUSED_TOO_LONG":
        return t("integrationsPage.alerts.pausedTooLong");
      default:
        return alert.type;
    }
  };

  const snippet = useMemo(() => {
    if (!createdEndpointInfo?.secret) return "";
    return [
      "POST https://your-endpoint",
      "Headers:",
      `X-Neft-Endpoint-ID: ${createdEndpointInfo.endpointId}`,
      "X-Neft-Timestamp: <unix_ms>",
      "X-Neft-Signature: hmac_sha256(secret, timestamp + '.' + raw_payload)",
      "",
      `Secret: ${createdEndpointInfo.secret}`,
    ].join("\n");
  }, [createdEndpointInfo]);

  if (!hasPartnerRole) {
    return <ForbiddenState />;
  }

  return (
    <div className="stack">
      <section className="card">
        <div className="section-title">
          <div>
            <h2>{t("integrationsPage.title")}</h2>
            <p className="muted">{t("integrationsPage.subtitle")}</p>
          </div>
          {isOwner ? (
            <button type="button" className="primary" onClick={() => setIsCreateOpen(true)}>
              {t("actions.createEndpoint")}
            </button>
          ) : null}
        </div>
        {endpointLoading ? (
          <LoadingState label={t("integrationsPage.loading.endpoints")} />
        ) : endpointError ? (
          <ErrorState
            description={formatErrorDescription(endpointError)}
            correlationId={endpointError.correlationId}
          />
        ) : endpoints.length === 0 ? (
          <EmptyState
            icon={<LinkIcon />}
            title={t("emptyStates.integrations.title")}
            description={t("emptyStates.integrations.description")}
            primaryAction={
              isOwner
                ? {
                    label: t("actions.createEndpoint"),
                    onClick: () => setIsCreateOpen(true),
                  }
                : undefined
            }
          />
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>{t("integrationsPage.table.url")}</th>
                <th>{t("common.status")}</th>
                <th>{t("integrationsPage.table.algorithm")}</th>
                <th>{t("integrationsPage.table.createdAt")}</th>
                <th>{t("common.actions")}</th>
              </tr>
            </thead>
            <tbody>
              {endpoints.map((endpoint) => (
                <tr key={endpoint.id}>
                  <td>{endpoint.url}</td>
                  <td>
                    <StatusBadge status={endpoint.status} />
                  </td>
                  <td>{endpoint.signing_algo ?? "HMAC_SHA256"}</td>
                  <td>{formatDateTime(endpoint.created_at)}</td>
                  <td>
                    <div className="stack-inline">
                      <button type="button" className="ghost" onClick={() => handleSelectEndpoint(endpoint.id)}>
                        {t("common.open")}
                      </button>
                      {isOwner ? (
                        <>
                          <button type="button" className="ghost" onClick={() => handleToggleEndpoint(endpoint)}>
                            {endpoint.status === "ACTIVE" ? t("integrationsPage.actions.disable") : t("integrationsPage.actions.enable")}
                          </button>
                          {endpoint.delivery_paused ? (
                            <button type="button" className="ghost" onClick={() => handleResumeEndpoint(endpoint)}>
                              {t("integrationsPage.actions.resume")}
                            </button>
                          ) : (
                            <button type="button" className="ghost" onClick={() => handlePauseEndpoint(endpoint)}>
                              {t("integrationsPage.actions.pause")}
                            </button>
                          )}
                          <button type="button" className="ghost" onClick={() => handleRotateSecret(endpoint)}>
                            {t("integrationsPage.actions.rotateSecret")}
                          </button>
                          <button type="button" className="ghost" onClick={() => handleTestPing(endpoint)}>
                            {t("integrationsPage.actions.testPing")}
                          </button>
                        </>
                      ) : null}
                      <button type="button" className="ghost" onClick={() => handleSelectEndpoint(endpoint.id)}>
                        {t("integrationsPage.actions.deliveries")}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="card">
        <div className="section-title">
          <div>
            <h2>{t("integrationsPage.deliveryHealth.title")}</h2>
            <p className="muted">{t("integrationsPage.deliveryHealth.subtitle")}</p>
          </div>
          {selectedEndpoint && isOwner ? (
            <div className="stack-inline">
              {selectedEndpoint.delivery_paused ? (
                <button type="button" className="ghost" onClick={() => handleResumeEndpoint(selectedEndpoint)}>
                  {t("integrationsPage.actions.resume")}
                </button>
              ) : (
                <button type="button" className="ghost" onClick={() => handlePauseEndpoint(selectedEndpoint)}>
                  {t("integrationsPage.actions.pause")}
                </button>
              )}
              <button type="button" className="ghost" onClick={() => setIsReplayOpen(true)}>
                {t("integrationsPage.actions.replay")}
              </button>
            </div>
          ) : null}
        </div>
        {!selectedEndpoint ? (
          <EmptyState
            icon={<LinkIcon />}
            title={t("integrationsPage.deliveryHealth.emptyTitle")}
            description={t("integrationsPage.deliveryHealth.emptyDescription")}
          />
        ) : slaLoading ? (
          <LoadingState label={t("integrationsPage.loading.sla")} />
        ) : slaError ? (
          <ErrorState description={formatErrorDescription(slaError)} correlationId={slaError.correlationId} />
        ) : slaStatus ? (
          <div className="stack">
            <div className="stack-inline">
              <div className="label">{t("integrationsPage.deliveryHealth.slaStatus")}</div>
              <StatusBadge status={slaStatus.success_ratio >= 0.8 ? "DELIVERED" : "FAILED"} />
              {selectedEndpoint.delivery_paused ? <StatusBadge status="PAUSED" /> : null}
            </div>
            <div className="stats-grid">
              <div className="notice">
                <div className="label">{t("integrationsPage.deliveryHealth.successRatio")}</div>
                <div>{Math.round(slaStatus.success_ratio * 100)}%</div>
              </div>
              <div className="notice">
                <div className="label">{t("integrationsPage.deliveryHealth.latency")}</div>
                <div>
                  {slaStatus.avg_latency_ms ?? t("common.notAvailable")}
                  {slaStatus.avg_latency_ms ? " ms" : ""}
                </div>
              </div>
              <div className="notice">
                <div className="label">{t("integrationsPage.deliveryHealth.breaches")}</div>
                <div>{slaStatus.sla_breaches}</div>
              </div>
            </div>
          </div>
        ) : null}
        {!isOwner ? <div className="notice small">{t("integrationsPage.ownerOnly")}</div> : null}
      </section>

      <section className="card">
        <div className="section-title">
          <div>
            <h2>{t("integrationsPage.alerts.title")}</h2>
            <p className="muted">{t("integrationsPage.alerts.subtitle")}</p>
          </div>
        </div>
        {!selectedEndpoint ? (
          <EmptyState
            icon={<LinkIcon />}
            title={t("integrationsPage.alerts.emptyTitle")}
            description={t("integrationsPage.alerts.emptyDescription")}
          />
        ) : alertsLoading ? (
          <LoadingState label={t("integrationsPage.loading.alerts")} />
        ) : alertsError ? (
          <ErrorState description={formatErrorDescription(alertsError)} correlationId={alertsError.correlationId} />
        ) : alerts.length === 0 ? (
          <div className="notice">{t("integrationsPage.alerts.noAlerts")}</div>
        ) : (
          <ul className="stack">
            {alerts.map((alert) => (
              <li key={alert.id} className="notice">
                <strong>{renderAlertMessage(alert)}</strong>
                <div className="muted small">{formatDateTime(alert.created_at)}</div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="card">
        <div className="section-title">
          <div>
            <h2>{t("integrationsPage.subscriptions.title")}</h2>
            <p className="muted">{t("integrationsPage.subscriptions.subtitle")}</p>
          </div>
          {selectedEndpoint ? (
            <div className="muted small">{t("integrationsPage.subscriptions.selectedEndpoint", { url: selectedEndpoint.url })}</div>
          ) : null}
        </div>
        {!selectedEndpoint ? (
          <EmptyState
            icon={<LinkIcon />}
            title={t("integrationsPage.subscriptions.emptyTitle")}
            description={t("integrationsPage.subscriptions.emptyDescription")}
          />
        ) : subscriptionLoading ? (
          <LoadingState label={t("integrationsPage.loading.subscriptions")} />
        ) : subscriptionError ? (
          <ErrorState
            description={formatErrorDescription(subscriptionError)}
            correlationId={subscriptionError.correlationId}
          />
        ) : (
          <div className="stack">
            <div className="notice">
              <strong>{t("integrationsPage.subscriptions.catalogTitle")}</strong>
              <span className="muted small">{t("integrationsPage.subscriptions.catalogNote")}</span>
            </div>
            <table className="data-table">
              <thead>
                <tr>
                  <th>{t("integrationsPage.subscriptions.table.eventType")}</th>
                  <th>{t("integrationsPage.subscriptions.table.enabled")}</th>
                  <th>{t("integrationsPage.subscriptions.table.filters")}</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {catalogEventTypes.map((eventType) => {
                  const subscription = subscriptions.find((item) => item.event_type === eventType);
                  const enabled = subscription?.enabled ?? false;
                  return (
                    <tr key={eventType}>
                      <td>{eventType}</td>
                      <td>
                        <label className="checkbox">
                          <input
                            type="checkbox"
                            checked={enabled}
                            disabled={!isOwner}
                          onChange={(event) => handleToggleSubscription(eventType, event.target.checked)}
                          />
                          {enabled ? t("integrationsPage.subscriptions.table.on") : t("integrationsPage.subscriptions.table.off")}
                        </label>
                      </td>
                      <td>
                        <textarea
                          className="textarea"
                          rows={3}
                          placeholder={t("integrationsPage.subscriptions.filtersPlaceholder")}
                          disabled={!isOwner}
                          value={subscriptionFiltersDraft[eventType] ?? ""}
                          onChange={(event) =>
                            setSubscriptionFiltersDraft((prev) => ({ ...prev, [eventType]: event.target.value }))
                          }
                        />
                      </td>
                      <td>
                        <div className="stack-inline">
                          {subscription && isOwner ? (
                            <button type="button" className="ghost" onClick={() => handleDeleteSubscription(subscription)}>
                              {t("actions.delete")}
                            </button>
                          ) : null}
                          {!subscription && isOwner ? (
                            <button type="button" className="ghost" onClick={() => handleToggleSubscription(eventType, true)}>
                              {t("actions.create")}
                            </button>
                          ) : null}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {!isOwner ? (
              <div className="notice small">
                {t("integrationsPage.subscriptions.ownerOnly")}
              </div>
            ) : null}
          </div>
        )}
      </section>

      <section className="card" ref={deliveriesRef}>
        <div className="section-title">
          <div>
            <h2>{t("integrationsPage.deliveries.title")}</h2>
            <p className="muted">{t("integrationsPage.deliveries.subtitle")}</p>
          </div>
          <div className="tabs">
            <button
              type="button"
              className={`tab ${deliveryTab === "history" ? "tab--active" : ""}`}
              onClick={() => setDeliveryTab("history")}
            >
              {t("integrationsPage.deliveries.tabs.history")}
            </button>
            <button
              type="button"
              className={`tab ${deliveryTab === "dlq" ? "tab--active" : ""}`}
              onClick={() => setDeliveryTab("dlq")}
            >
              DLQ
            </button>
          </div>
        </div>

        {!selectedEndpoint ? (
          <EmptyState
            icon={<LinkIcon />}
            title={t("integrationsPage.deliveries.emptyTitle")}
            description={t("integrationsPage.deliveries.emptyDescription")}
          />
        ) : (
          <>
            <div className="filters">
              <label className="filter">
                {t("integrationsPage.deliveries.filters.endpoint")}
                <select
                  value={selectedEndpointId ?? ""}
                  onChange={(event) => setSelectedEndpointId(event.target.value)}
                >
                  {endpoints.map((endpoint) => (
                    <option key={endpoint.id} value={endpoint.id}>
                      {endpoint.url}
                    </option>
                  ))}
                </select>
              </label>
              {deliveryTab === "history" ? (
                <label className="filter">
                  {t("integrationsPage.deliveries.filters.status")}
                  <select
                    value={deliveryFilters.status}
                    onChange={(event) => setDeliveryFilters((prev) => ({ ...prev, status: event.target.value }))}
                  >
                    <option value="">{t("common.all")}</option>
                    <option value="DELIVERED">{t("statuses.webhooks.DELIVERED")}</option>
                    <option value="FAILED">{t("statuses.webhooks.FAILED")}</option>
                    <option value="DEAD">{t("statuses.webhooks.DEAD")}</option>
                    <option value="PAUSED">{t("statuses.webhooks.PAUSED")}</option>
                  </select>
                </label>
              ) : null}
              <label className="filter">
                {t("integrationsPage.deliveries.filters.eventType")}
                <input
                  type="text"
                  value={deliveryFilters.eventType}
                  onChange={(event) => setDeliveryFilters((prev) => ({ ...prev, eventType: event.target.value }))}
                  placeholder={t("integrationsPage.deliveries.filters.eventTypePlaceholder")}
                />
              </label>
              <label className="filter">
                {t("integrationsPage.deliveries.filters.eventId")}
                <input
                  type="text"
                  value={deliveryFilters.eventId}
                  onChange={(event) => setDeliveryFilters((prev) => ({ ...prev, eventId: event.target.value }))}
                  placeholder={t("integrationsPage.deliveries.filters.eventIdPlaceholder")}
                />
              </label>
              <label className="filter">
                {t("integrationsPage.deliveries.filters.from")}
                <input
                  type="date"
                  value={deliveryFilters.from}
                  onChange={(event) => setDeliveryFilters((prev) => ({ ...prev, from: event.target.value }))}
                />
              </label>
              <label className="filter">
                {t("integrationsPage.deliveries.filters.to")}
                <input
                  type="date"
                  value={deliveryFilters.to}
                  onChange={(event) => setDeliveryFilters((prev) => ({ ...prev, to: event.target.value }))}
                />
              </label>
            </div>

            {deliveryLoading ? (
              <LoadingState label={t("integrationsPage.loading.deliveries")} />
            ) : deliveryError ? (
              <ErrorState
                description={formatErrorDescription(deliveryError)}
                correlationId={deliveryError.correlationId}
              />
            ) : deliveries.length === 0 ? (
              <EmptyState
                icon={<LinkIcon />}
                title={t("integrationsPage.deliveries.noDeliveriesTitle")}
                description={t("integrationsPage.deliveries.noDeliveriesDescription")}
              />
            ) : (
              <div className="stack">
                {deliveryTab === "dlq" && isOwner ? (
                  <div className="notice">
                    <strong>{t("integrationsPage.deliveries.dlqTitle")}</strong>
                    <span className="muted small">
                      {t("integrationsPage.deliveries.dlqNote")}
                    </span>
                    <div>
                      <button type="button" className="ghost" onClick={handleBulkRetry}>
                        {t("integrationsPage.deliveries.retryAll")}
                      </button>
                    </div>
                  </div>
                ) : null}
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>{t("integrationsPage.deliveries.table.occurredAt")}</th>
                      <th>{t("integrationsPage.deliveries.table.eventType")}</th>
                      <th>{t("common.status")}</th>
                      <th>{t("integrationsPage.deliveries.table.attempt")}</th>
                      <th>{t("integrationsPage.deliveries.table.http")}</th>
                      <th>{t("integrationsPage.deliveries.table.latency")}</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {deliveries.map((delivery) => (
                      <tr key={delivery.id}>
                        <td>{formatDateTime(delivery.occurred_at)}</td>
                        <td>{delivery.event_type}</td>
                        <td>
                          <StatusBadge status={delivery.status} />
                        </td>
                        <td>{delivery.attempt ?? t("common.notAvailable")}</td>
                        <td>{delivery.last_http_status ?? t("common.notAvailable")}</td>
                        <td>{delivery.latency_ms ?? t("common.notAvailable")}</td>
                        <td>
                          <div className="stack-inline">
                            <button type="button" className="ghost" onClick={() => handleOpenDeliveryDetail(delivery)}>
                              {t("integrationsPage.deliveries.actions.detail")}
                            </button>
                            {isOwner && ["FAILED", "DEAD"].includes(delivery.status) ? (
                              <button type="button" className="ghost" onClick={() => handleRetryDelivery(delivery)}>
                                {t("actions.retry")}
                              </button>
                            ) : null}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </section>

      {isCreateOpen ? (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal">
            <div className="card__header">
              <h3>{t("integrationsPage.modals.create.title")}</h3>
              <button type="button" className="ghost" onClick={() => setIsCreateOpen(false)}>
                {t("actions.close")}
              </button>
            </div>
            <div className="form-grid">
              <label className="form-field">
                {t("integrationsPage.modals.create.url")}
                <input
                  type="url"
                  placeholder={t("integrationsPage.modals.create.urlPlaceholder")}
                  value={createForm.url}
                  onChange={(event) => setCreateForm((prev) => ({ ...prev, url: event.target.value }))}
                />
              </label>
              <label className="form-field">
                {t("integrationsPage.modals.create.signingAlgo")}
                <select
                  value={createForm.signingAlgo}
                  onChange={(event) => setCreateForm((prev) => ({ ...prev, signingAlgo: event.target.value }))}
                >
                  <option value="HMAC_SHA256">HMAC_SHA256</option>
                </select>
              </label>
              <label className="checkbox">
                <input
                  type="checkbox"
                  checked={createForm.enabled}
                  onChange={(event) => setCreateForm((prev) => ({ ...prev, enabled: event.target.checked }))}
                />
                {t("integrationsPage.modals.create.enabled")}
              </label>
            </div>
            {createError ? (
              <div className="notice error">
                {formatErrorDescription(createError)}
              </div>
            ) : null}
            <div className="form-actions">
              <button type="button" className="primary" onClick={handleCreateEndpoint}>
                {t("actions.create")}
              </button>
              <button type="button" className="ghost" onClick={() => setIsCreateOpen(false)}>
                {t("actions.cancel")}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {createdEndpointInfo ? (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal">
            <div className="card__header">
              <h3>{t("integrationsPage.modals.created.title")}</h3>
              <button type="button" className="ghost" onClick={() => setCreatedEndpointInfo(null)}>
                {t("actions.close")}
              </button>
            </div>
            <div className="stack">
              <div className="notice">
                <div className="label">{t("integrationsPage.modals.created.endpointId")}</div>
                <div>{createdEndpointInfo.endpointId}</div>
              </div>
              <div className="notice">
                <div className="label">{t("integrationsPage.modals.created.secret")}</div>
                <div className="stack-inline">
                  <span className="mono">{createdEndpointInfo.secret}</span>
                  <CopyButton value={createdEndpointInfo.secret} label={t("integrationsPage.modals.created.copySecret")} />
                </div>
              </div>
              <div>
                <div className="label">{t("integrationsPage.modals.created.snippet")}</div>
                <pre className="code-block">{snippet}</pre>
                <CopyButton value={snippet} label={t("integrationsPage.modals.created.copySnippet")} />
              </div>
            </div>
          </div>
        </div>
      ) : null}

      {isReplayOpen ? (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal">
            <div className="card__header">
              <h3>{t("integrationsPage.modals.replay.title")}</h3>
              <button type="button" className="ghost" onClick={() => setIsReplayOpen(false)}>
                {t("actions.close")}
              </button>
            </div>
            <div className="form-grid">
              <label className="form-field">
                {t("integrationsPage.modals.replay.from")}
                <input
                  type="datetime-local"
                  value={replayForm.from}
                  onChange={(event) => setReplayForm((prev) => ({ ...prev, from: event.target.value }))}
                />
              </label>
              <label className="form-field">
                {t("integrationsPage.modals.replay.to")}
                <input
                  type="datetime-local"
                  value={replayForm.to}
                  onChange={(event) => setReplayForm((prev) => ({ ...prev, to: event.target.value }))}
                />
              </label>
              <label className="form-field">
                {t("integrationsPage.modals.replay.eventTypes")}
                <input
                  type="text"
                  placeholder={t("integrationsPage.modals.replay.eventTypesPlaceholder")}
                  value={replayForm.eventTypes}
                  onChange={(event) => setReplayForm((prev) => ({ ...prev, eventTypes: event.target.value }))}
                />
              </label>
              <label className="checkbox">
                <input
                  type="checkbox"
                  checked={replayForm.onlyFailed}
                  onChange={(event) => setReplayForm((prev) => ({ ...prev, onlyFailed: event.target.checked }))}
                />
                {t("integrationsPage.modals.replay.onlyFailed")}
              </label>
            </div>
            {replayError ? (
              <div className="notice error">{formatErrorDescription(replayError)}</div>
            ) : null}
            {replayResult ? (
              <div className="notice">
                {t("integrationsPage.modals.replay.result", {
                  count: replayResult.scheduled,
                  replayId: replayResult.replayId,
                })}
              </div>
            ) : null}
            <div className="form-actions">
              <button type="button" className="primary" onClick={handleReplay}>
                {t("integrationsPage.actions.replay")}
              </button>
              <button type="button" className="ghost" onClick={() => setIsReplayOpen(false)}>
                {t("actions.cancel")}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {rotatedSecretInfo ? (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal">
            <div className="card__header">
              <h3>{t("integrationsPage.modals.rotated.title")}</h3>
              <button type="button" className="ghost" onClick={() => setRotatedSecretInfo(null)}>
                {t("actions.close")}
              </button>
            </div>
            <div className="stack">
              <div className="notice">
                <div className="label">{t("integrationsPage.modals.rotated.endpointId")}</div>
                <div>{rotatedSecretInfo.endpointId}</div>
              </div>
              <div className="notice error">
                {t("integrationsPage.modals.rotated.notice")}
              </div>
              <div className="notice">
                <div className="label">{t("integrationsPage.modals.rotated.newSecret")}</div>
                <div className="stack-inline">
                  <span className="mono">{rotatedSecretInfo.secret}</span>
                  <CopyButton value={rotatedSecretInfo.secret} label={t("integrationsPage.modals.rotated.copySecret")} />
                </div>
              </div>
            </div>
          </div>
        </div>
      ) : null}

      {testPingResult ? (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal">
            <div className="card__header">
              <h3>{t("integrationsPage.modals.testPing.title")}</h3>
              <button type="button" className="ghost" onClick={() => setTestPingResult(null)}>
                {t("actions.close")}
              </button>
            </div>
            <div className="stack">
              <div className="notice">
                <div className="label">{t("integrationsPage.modals.testPing.deliveryId")}</div>
                <div>{testPingResult.result.delivery_id}</div>
              </div>
              <div className="notice">
                <div className="label">{t("integrationsPage.modals.testPing.httpStatus")}</div>
                <div>{testPingResult.result.http_status ?? t("common.notAvailable")}</div>
              </div>
              <div className="notice">
                <div className="label">{t("integrationsPage.modals.testPing.latency")}</div>
                <div>{testPingResult.result.latency_ms ?? t("common.notAvailable")} ms</div>
              </div>
              {testPingResult.result.error ? (
                <div className="notice error">{t("integrationsPage.errors.sendTestFailed")}</div>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}

      {isDeliveryDetailOpen ? (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal modal--wide">
            <div className="card__header">
              <h3>{t("integrationsPage.modals.deliveryDetail.title")}</h3>
              <button
                type="button"
                className="ghost"
                onClick={() => {
                  setIsDeliveryDetailOpen(false);
                  setDeliveryDetail(null);
                  setDeliveryDetailError(null);
                }}
              >
                {t("actions.close")}
              </button>
            </div>
            {deliveryDetailLoading ? (
              <LoadingState label={t("integrationsPage.loading.deliveryDetail")} />
            ) : deliveryDetailError ? (
              <ErrorState
                description={formatErrorDescription(deliveryDetailError)}
                correlationId={deliveryDetailError.correlationId}
              />
            ) : deliveryDetail ? (
              <div className="stack">
                <div className="meta-grid">
                  <div>
                    <div className="label">{t("integrationsPage.modals.deliveryDetail.endpointUrl")}</div>
                    <div>{deliveryDetail.endpoint_url ?? t("common.notAvailable")}</div>
                  </div>
                  <div>
                    <div className="label">{t("integrationsPage.modals.deliveryDetail.eventType")}</div>
                    <div>{deliveryDetail.event_type}</div>
                  </div>
                  <div>
                    <div className="label">{t("common.status")}</div>
                    <StatusBadge status={deliveryDetail.status} />
                  </div>
                </div>
                <div className="grid two">
                  <div>
                    <div className="label">{t("integrationsPage.modals.deliveryDetail.envelope")}</div>
                    <pre className="code-block">{JSON.stringify(deliveryDetail.envelope ?? {}, null, 2)}</pre>
                  </div>
                  <div>
                    <div className="label">{t("integrationsPage.modals.deliveryDetail.headers")}</div>
                    <pre className="code-block">{JSON.stringify(deliveryDetail.headers ?? {}, null, 2)}</pre>
                  </div>
                </div>
                <div>
                  <div className="label">{t("integrationsPage.modals.deliveryDetail.attempts")}</div>
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>#</th>
                        <th>{t("integrationsPage.modals.deliveryDetail.table.http")}</th>
                        <th>{t("integrationsPage.modals.deliveryDetail.table.error")}</th>
                        <th>{t("integrationsPage.modals.deliveryDetail.table.latency")}</th>
                        <th>{t("integrationsPage.modals.deliveryDetail.table.nextRetry")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(deliveryDetail.attempts ?? []).map((attempt) => (
                        <tr key={`${deliveryDetail.id}-${attempt.attempt}`}>
                          <td>{attempt.attempt}</td>
                          <td>{attempt.http_status ?? t("common.notAvailable")}</td>
                          <td>{attempt.error ? t("integrationsPage.modals.deliveryDetail.table.deliveryError") : t("common.notAvailable")}</td>
                          <td>{attempt.latency_ms ?? t("common.notAvailable")} ms</td>
                          <td>{attempt.next_retry_at ? formatDateTime(attempt.next_retry_at) : t("common.notAvailable")}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {isOwner && ["FAILED", "DEAD"].includes(deliveryDetail.status) ? (
                  <button type="button" className="primary" onClick={() => handleRetryDelivery(deliveryDetail)}>
                    {t("integrationsPage.deliveries.actions.retry")}
                  </button>
                ) : null}
                <button type="button" className="secondary" onClick={() => setIsSupportOpen(true)}>
                  {t("supportRequests.modal.title")}
                </button>
              </div>
            ) : (
              <LoadingState label={t("integrationsPage.loading.deliveryDetailPending")} />
            )}
          </div>
        </div>
      ) : null}
      <SupportRequestModal
        isOpen={isSupportOpen}
        onClose={() => setIsSupportOpen(false)}
        subjectType="INTEGRATION"
        subjectId={deliveryDetail?.id ?? null}
        correlationId={deliveryDetail?.correlation_id ?? undefined}
        defaultTitle={deliveryDetail ? `Webhook delivery ${deliveryDetail.id}` : "Webhook delivery"}
      />
    </div>
  );
}
