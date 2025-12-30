import { useEffect, useMemo, useRef, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { EmptyState, ErrorState, ForbiddenState, LoadingState } from "../components/states";
import { StatusBadge } from "../components/StatusBadge";
import { CopyButton } from "../components/CopyButton";
import { defaultWebhookEvents } from "../constants/webhookEvents";
import {
  createWebhookEndpoint,
  createWebhookSubscription,
  deleteWebhookSubscription,
  fetchWebhookEventTypes,
  fetchWebhookDeliveries,
  fetchWebhookDeliveryDetail,
  fetchWebhookEndpoints,
  fetchWebhookSubscriptions,
  retryWebhookDelivery,
  rotateWebhookSecret,
  sendWebhookTest,
  updateWebhookEndpointStatus,
  updateWebhookSubscription,
} from "../api/webhooks";
import { ApiError } from "../api/http";
import type {
  WebhookDelivery,
  WebhookDeliveryDetail,
  WebhookEndpoint,
  WebhookSubscription,
  WebhookTestResult,
} from "../types/webhooks";

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
    parts.push(`HTTP ${error.status}`);
  }
  return parts.join(" · ");
};

const formatDateTime = (value: string | null | undefined) => {
  if (!value) return "—";
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
  const [isDeliveryDetailOpen, setIsDeliveryDetailOpen] = useState(false);

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
      .catch((err) => setEndpointError(normalizeError(err, "Не удалось загрузить endpoints")))
      .finally(() => setEndpointLoading(false));
  }, [user, selectedEndpointId]);

  useEffect(() => {
    if (!user) return;
    fetchWebhookEventTypes(user.token)
      .then((data) => {
        if (data.length > 0) {
          setEventTypes(data);
        }
      })
      .catch((err) => {
        console.warn("Не удалось загрузить список событий, используем список по умолчанию", err);
      });
  }, [user]);

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
      .catch((err) => setSubscriptionError(normalizeError(err, "Не удалось загрузить подписки")))
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
      .catch((err) => setDeliveryError(normalizeError(err, "Не удалось загрузить доставки")))
      .finally(() => setDeliveryLoading(false));
  }, [deliveryFilters, deliveryTab, selectedEndpointId, user]);

  const handleCreateEndpoint = async () => {
    if (!user) return;
    setCreateError(null);
    if (!/^https?:\/\//.test(createForm.url)) {
      setCreateError({ message: "URL должен начинаться с http:// или https://" });
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
      setCreateError(normalizeError(err, "Не удалось создать endpoint"));
    }
  };

  const handleToggleEndpoint = async (endpoint: WebhookEndpoint) => {
    if (!user) return;
    const nextStatus = endpoint.status === "ACTIVE" ? "DISABLED" : "ACTIVE";
    const confirmation = window.confirm(
      nextStatus === "DISABLED"
        ? "Отключить endpoint? Доставки будут остановлены."
        : "Включить endpoint?",
    );
    if (!confirmation) return;
    try {
      await updateWebhookEndpointStatus(user.token, endpoint.id, nextStatus);
      setEndpoints((prev) =>
        prev.map((item) => (item.id === endpoint.id ? { ...item, status: nextStatus } : item)),
      );
    } catch (err) {
      setEndpointError(normalizeError(err, "Не удалось обновить статус endpoint"));
    }
  };

  const handleRotateSecret = async (endpoint: WebhookEndpoint) => {
    if (!user) return;
    const confirmation = window.confirm("Секрет будет заменён. Старый секрет перестанет работать. Продолжить?");
    if (!confirmation) return;
    try {
      const response = await rotateWebhookSecret(user.token, endpoint.id);
      setRotatedSecretInfo({
        endpointId: endpoint.id,
        secret: response.data.secret,
        correlationId: response.correlationId,
      });
    } catch (err) {
      setEndpointError(normalizeError(err, "Не удалось ротировать секрет"));
    }
  };

  const handleTestPing = async (endpoint: WebhookEndpoint) => {
    if (!user) return;
    try {
      const response = await sendWebhookTest(user.token, endpoint.id, "test.ping");
      setTestPingResult({ endpointId: endpoint.id, result: response.data, correlationId: response.correlationId });
    } catch (err) {
      setEndpointError(normalizeError(err, "Не удалось отправить тестовый webhook"));
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
          setSubscriptionError({ message: "Некорректный JSON в фильтрах" });
          return;
        }
        const created = await createWebhookSubscription(user.token, selectedEndpointId, eventType, enabled, filters);
        setSubscriptions((prev) => [...prev, created]);
      }
    } catch (err) {
      setSubscriptionError(normalizeError(err, "Не удалось обновить подписку"));
    }
  };

  const handleDeleteSubscription = async (subscription: WebhookSubscription) => {
    if (!user) return;
    const confirmation = window.confirm("Удалить подписку?");
    if (!confirmation) return;
    try {
      await deleteWebhookSubscription(user.token, subscription.id);
      setSubscriptions((prev) => prev.filter((item) => item.id !== subscription.id));
    } catch (err) {
      setSubscriptionError(normalizeError(err, "Не удалось удалить подписку"));
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
      setDeliveryDetailError(normalizeError(err, "Не удалось загрузить детали доставки"));
    } finally {
      setDeliveryDetailLoading(false);
    }
  };

  const handleRetryDelivery = async (delivery: WebhookDelivery) => {
    if (!user) return;
    const confirmation = window.confirm("Повторить доставку?");
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
      setDeliveryError(normalizeError(err, "Не удалось повторить доставку"));
    }
  };

  const handleBulkRetry = async () => {
    if (!user) return;
    const confirmation = window.confirm("Повторить все dead deliveries? Это приведёт к повторной доставке.");
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
      setDeliveryError(normalizeError(err, "Не удалось выполнить повторную доставку"));
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
            <h2>Integrations · Webhooks</h2>
            <p className="muted">Integration Hub v1 · Self-service</p>
          </div>
          {isOwner ? (
            <button type="button" className="primary" onClick={() => setIsCreateOpen(true)}>
              Создать endpoint
            </button>
          ) : null}
        </div>
        {endpointLoading ? (
          <LoadingState label="Загружаем endpoints..." />
        ) : endpointError ? (
          <ErrorState
            description={formatErrorDescription(endpointError)}
            correlationId={endpointError.correlationId}
          />
        ) : endpoints.length === 0 ? (
          <EmptyState
            title="Webhook endpoints ещё не созданы"
            description="Создайте первый endpoint, чтобы начать получать события."
            action={
              isOwner ? (
                <button type="button" className="primary" onClick={() => setIsCreateOpen(true)}>
                  Создать endpoint
                </button>
              ) : null
            }
          />
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>URL</th>
                <th>Статус</th>
                <th>Алгоритм</th>
                <th>Создан</th>
                <th>Действия</th>
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
                        Открыть
                      </button>
                      {isOwner ? (
                        <>
                          <button type="button" className="ghost" onClick={() => handleToggleEndpoint(endpoint)}>
                            {endpoint.status === "ACTIVE" ? "Disable" : "Enable"}
                          </button>
                          <button type="button" className="ghost" onClick={() => handleRotateSecret(endpoint)}>
                            Rotate secret
                          </button>
                          <button type="button" className="ghost" onClick={() => handleTestPing(endpoint)}>
                            Test ping
                          </button>
                        </>
                      ) : null}
                      <button type="button" className="ghost" onClick={() => handleSelectEndpoint(endpoint.id)}>
                        Deliveries
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
            <h2>Subscriptions</h2>
            <p className="muted">Выберите события для выбранного endpoint.</p>
          </div>
          {selectedEndpoint ? (
            <div className="muted small">Endpoint: {selectedEndpoint.url}</div>
          ) : null}
        </div>
        {!selectedEndpoint ? (
          <EmptyState title="Сначала выберите endpoint" description="Выберите endpoint в списке выше." />
        ) : subscriptionLoading ? (
          <LoadingState label="Загружаем подписки..." />
        ) : subscriptionError ? (
          <ErrorState
            description={formatErrorDescription(subscriptionError)}
            correlationId={subscriptionError.correlationId}
          />
        ) : (
          <div className="stack">
            <div className="notice">
              <strong>Каталог событий</strong>
              <span className="muted small">Фильтры передаются в Integration Hub без обработки на фронте.</span>
            </div>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Event type</th>
                  <th>Enabled</th>
                  <th>Filters (JSON)</th>
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
                          {enabled ? "On" : "Off"}
                        </label>
                      </td>
                      <td>
                        <textarea
                          className="textarea"
                          rows={3}
                          placeholder='{"station_id":"..."}'
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
                              Delete
                            </button>
                          ) : null}
                          {!subscription && isOwner ? (
                            <button type="button" className="ghost" onClick={() => handleToggleSubscription(eventType, true)}>
                              Create
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
                Изменение подписок доступно только роли PARTNER_OWNER.
              </div>
            ) : null}
          </div>
        )}
      </section>

      <section className="card" ref={deliveriesRef}>
        <div className="section-title">
          <div>
            <h2>Deliveries</h2>
            <p className="muted">История доставок и DLQ.</p>
          </div>
          <div className="tabs">
            <button
              type="button"
              className={`tab ${deliveryTab === "history" ? "tab--active" : ""}`}
              onClick={() => setDeliveryTab("history")}
            >
              История
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
          <EmptyState title="Нет выбранного endpoint" description="Выберите endpoint для просмотра доставок." />
        ) : (
          <>
            <div className="filters">
              <label className="filter">
                Endpoint
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
                  Status
                  <select
                    value={deliveryFilters.status}
                    onChange={(event) => setDeliveryFilters((prev) => ({ ...prev, status: event.target.value }))}
                  >
                    <option value="">Все</option>
                    <option value="DELIVERED">DELIVERED</option>
                    <option value="FAILED">FAILED</option>
                    <option value="DEAD">DEAD</option>
                  </select>
                </label>
              ) : null}
              <label className="filter">
                Event type
                <input
                  type="text"
                  value={deliveryFilters.eventType}
                  onChange={(event) => setDeliveryFilters((prev) => ({ ...prev, eventType: event.target.value }))}
                  placeholder="payout.*"
                />
              </label>
              <label className="filter">
                Event ID
                <input
                  type="text"
                  value={deliveryFilters.eventId}
                  onChange={(event) => setDeliveryFilters((prev) => ({ ...prev, eventId: event.target.value }))}
                  placeholder="event-123"
                />
              </label>
              <label className="filter">
                From
                <input
                  type="date"
                  value={deliveryFilters.from}
                  onChange={(event) => setDeliveryFilters((prev) => ({ ...prev, from: event.target.value }))}
                />
              </label>
              <label className="filter">
                To
                <input
                  type="date"
                  value={deliveryFilters.to}
                  onChange={(event) => setDeliveryFilters((prev) => ({ ...prev, to: event.target.value }))}
                />
              </label>
            </div>

            {deliveryLoading ? (
              <LoadingState label="Загружаем доставки..." />
            ) : deliveryError ? (
              <ErrorState
                description={formatErrorDescription(deliveryError)}
                correlationId={deliveryError.correlationId}
              />
            ) : deliveries.length === 0 ? (
              <EmptyState title="Нет доставок" description="Когда появятся события, они будут здесь." />
            ) : (
              <div className="stack">
                {deliveryTab === "dlq" && isOwner ? (
                  <div className="notice">
                    <strong>Dead Letter Queue</strong>
                    <span className="muted small">
                      Повторная доставка приведёт к повторной отправке всех событий.
                    </span>
                    <div>
                      <button type="button" className="ghost" onClick={handleBulkRetry}>
                        Retry selected (all)
                      </button>
                    </div>
                  </div>
                ) : null}
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Occurred at</th>
                      <th>Event type</th>
                      <th>Status</th>
                      <th>Attempt</th>
                      <th>HTTP</th>
                      <th>Latency, ms</th>
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
                        <td>{delivery.attempt ?? "—"}</td>
                        <td>{delivery.last_http_status ?? "—"}</td>
                        <td>{delivery.latency_ms ?? "—"}</td>
                        <td>
                          <div className="stack-inline">
                            <button type="button" className="ghost" onClick={() => handleOpenDeliveryDetail(delivery)}>
                              Detail
                            </button>
                            {isOwner && ["FAILED", "DEAD"].includes(delivery.status) ? (
                              <button type="button" className="ghost" onClick={() => handleRetryDelivery(delivery)}>
                                Retry
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
              <h3>Create endpoint</h3>
              <button type="button" className="ghost" onClick={() => setIsCreateOpen(false)}>
                Close
              </button>
            </div>
            <div className="form-grid">
              <label className="form-field">
                URL
                <input
                  type="url"
                  placeholder="https://partner.example/webhooks"
                  value={createForm.url}
                  onChange={(event) => setCreateForm((prev) => ({ ...prev, url: event.target.value }))}
                />
              </label>
              <label className="form-field">
                Signing algo
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
                Endpoint enabled
              </label>
            </div>
            {createError ? (
              <div className="notice error">
                {formatErrorDescription(createError)}
                {createError.correlationId ? (
                  <div className="muted small">Correlation ID: {createError.correlationId}</div>
                ) : null}
              </div>
            ) : null}
            <div className="form-actions">
              <button type="button" className="primary" onClick={handleCreateEndpoint}>
                Создать
              </button>
              <button type="button" className="ghost" onClick={() => setIsCreateOpen(false)}>
                Отмена
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {createdEndpointInfo ? (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal">
            <div className="card__header">
              <h3>Endpoint created</h3>
              <button type="button" className="ghost" onClick={() => setCreatedEndpointInfo(null)}>
                Close
              </button>
            </div>
            <div className="stack">
              <div className="notice">
                <div className="label">Endpoint ID</div>
                <div>{createdEndpointInfo.endpointId}</div>
              </div>
              <div className="notice">
                <div className="label">Secret (one-time view)</div>
                <div className="stack-inline">
                  <span className="mono">{createdEndpointInfo.secret}</span>
                  <CopyButton value={createdEndpointInfo.secret} label="Copy secret" />
                </div>
              </div>
              <div>
                <div className="label">Setup snippet</div>
                <pre className="code-block">{snippet}</pre>
                <CopyButton value={snippet} label="Copy setup snippet" />
              </div>
              {createdEndpointInfo.correlationId ? (
                <div className="muted small">Correlation ID: {createdEndpointInfo.correlationId}</div>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}

      {rotatedSecretInfo ? (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal">
            <div className="card__header">
              <h3>Secret rotated</h3>
              <button type="button" className="ghost" onClick={() => setRotatedSecretInfo(null)}>
                Close
              </button>
            </div>
            <div className="stack">
              <div className="notice">
                <div className="label">Endpoint ID</div>
                <div>{rotatedSecretInfo.endpointId}</div>
              </div>
              <div className="notice error">
                Старый секрет больше не действует. Используйте новый секрет ниже.
              </div>
              <div className="notice">
                <div className="label">New secret</div>
                <div className="stack-inline">
                  <span className="mono">{rotatedSecretInfo.secret}</span>
                  <CopyButton value={rotatedSecretInfo.secret} label="Copy secret" />
                </div>
              </div>
              {rotatedSecretInfo.correlationId ? (
                <div className="muted small">Correlation ID: {rotatedSecretInfo.correlationId}</div>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}

      {testPingResult ? (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal">
            <div className="card__header">
              <h3>Test ping</h3>
              <button type="button" className="ghost" onClick={() => setTestPingResult(null)}>
                Close
              </button>
            </div>
            <div className="stack">
              <div className="notice">
                <div className="label">Delivery ID</div>
                <div>{testPingResult.result.delivery_id}</div>
              </div>
              <div className="notice">
                <div className="label">HTTP status</div>
                <div>{testPingResult.result.http_status ?? "—"}</div>
              </div>
              <div className="notice">
                <div className="label">Latency</div>
                <div>{testPingResult.result.latency_ms ?? "—"} ms</div>
              </div>
              {testPingResult.result.error ? (
                <div className="notice error">{testPingResult.result.error}</div>
              ) : null}
              {testPingResult.correlationId ? (
                <div className="muted small">Correlation ID: {testPingResult.correlationId}</div>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}

      {isDeliveryDetailOpen ? (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal modal--wide">
            <div className="card__header">
              <h3>Delivery detail</h3>
              <button
                type="button"
                className="ghost"
                onClick={() => {
                  setIsDeliveryDetailOpen(false);
                  setDeliveryDetail(null);
                  setDeliveryDetailError(null);
                }}
              >
                Close
              </button>
            </div>
            {deliveryDetailLoading ? (
              <LoadingState label="Загружаем детали..." />
            ) : deliveryDetailError ? (
              <ErrorState
                description={formatErrorDescription(deliveryDetailError)}
                correlationId={deliveryDetailError.correlationId}
              />
            ) : deliveryDetail ? (
              <div className="stack">
                <div className="meta-grid">
                  <div>
                    <div className="label">Endpoint URL</div>
                    <div>{deliveryDetail.endpoint_url ?? "—"}</div>
                  </div>
                  <div>
                    <div className="label">Event type</div>
                    <div>{deliveryDetail.event_type}</div>
                  </div>
                  <div>
                    <div className="label">Status</div>
                    <StatusBadge status={deliveryDetail.status} />
                  </div>
                  <div>
                    <div className="label">Correlation ID</div>
                    <div>{deliveryDetail.correlation_id ?? "—"}</div>
                  </div>
                </div>
                <div className="grid two">
                  <div>
                    <div className="label">Envelope</div>
                    <pre className="code-block">{JSON.stringify(deliveryDetail.envelope ?? {}, null, 2)}</pre>
                  </div>
                  <div>
                    <div className="label">Headers</div>
                    <pre className="code-block">{JSON.stringify(deliveryDetail.headers ?? {}, null, 2)}</pre>
                  </div>
                </div>
                <div>
                  <div className="label">Attempts</div>
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>#</th>
                        <th>HTTP</th>
                        <th>Error</th>
                        <th>Latency</th>
                        <th>Next retry</th>
                        <th>Correlation ID</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(deliveryDetail.attempts ?? []).map((attempt) => (
                        <tr key={`${deliveryDetail.id}-${attempt.attempt}`}>
                          <td>{attempt.attempt}</td>
                          <td>{attempt.http_status ?? "—"}</td>
                          <td>{attempt.error ?? "—"}</td>
                          <td>{attempt.latency_ms ?? "—"} ms</td>
                          <td>{attempt.next_retry_at ? formatDateTime(attempt.next_retry_at) : "—"}</td>
                          <td>{attempt.correlation_id ?? "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {isOwner && ["FAILED", "DEAD"].includes(deliveryDetail.status) ? (
                  <button type="button" className="primary" onClick={() => handleRetryDelivery(deliveryDetail)}>
                    Retry delivery
                  </button>
                ) : null}
              </div>
            ) : (
              <LoadingState label="Готовим детали..." />
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
