import { request, requestWithMeta, type ApiResponse } from "./http";
import type {
  WebhookDelivery,
  WebhookDeliveryDetail,
  WebhookAlert,
  WebhookEndpoint,
  WebhookEndpointCreatePayload,
  WebhookEndpointCreateResponse,
  WebhookEndpointSecretResponse,
  WebhookReplayPayload,
  WebhookReplayResult,
  WebhookSlaStatus,
  WebhookSubscription,
  WebhookTestResult,
} from "../types/webhooks";

const buildQuery = (params: Record<string, string | number | null | undefined>): string => {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") return;
    search.set(key, String(value));
  });
  const query = search.toString();
  return query ? `?${query}` : "";
};

type ListResponse<T> = { items?: T[] } | T[];

const normalizeList = <T>(payload: ListResponse<T>): T[] => {
  if (Array.isArray(payload)) return payload;
  return payload.items ?? [];
};

export async function fetchWebhookEndpoints(token: string, ownerId: string): Promise<WebhookEndpoint[]> {
  const data = await request<ListResponse<WebhookEndpoint>>(
    `/v1/webhooks/endpoints${buildQuery({ owner_type: "PARTNER", owner_id: ownerId })}`,
    {},
    token,
  );
  return normalizeList(data);
}

export async function fetchWebhookEventTypes(token: string): Promise<string[]> {
  const data = await request<ListResponse<string>>(
    `/v1/webhooks/event-types${buildQuery({ owner_type: "PARTNER" })}`,
    {},
    token,
  );
  return normalizeList(data);
}

export async function createWebhookEndpoint(
  token: string,
  payload: WebhookEndpointCreatePayload,
): Promise<ApiResponse<WebhookEndpointCreateResponse>> {
  return requestWithMeta<WebhookEndpointCreateResponse>(
    "/v1/webhooks/endpoints",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    token,
  );
}

export async function updateWebhookEndpointStatus(
  token: string,
  endpointId: string,
  status: "ACTIVE" | "DISABLED",
  url?: string,
): Promise<void> {
  await request(
    `/v1/webhooks/endpoints/${endpointId}`,
    {
      method: "PATCH",
      body: JSON.stringify({ status, ...(url ? { url } : {}) }),
    },
    token,
  );
}

export async function rotateWebhookSecret(
  token: string,
  endpointId: string,
): Promise<ApiResponse<WebhookEndpointSecretResponse>> {
  return requestWithMeta<WebhookEndpointSecretResponse>(
    `/v1/webhooks/endpoints/${endpointId}/rotate-secret`,
    { method: "POST" },
    token,
  );
}

export async function sendWebhookTest(
  token: string,
  endpointId: string,
  eventType: string,
  payload?: Record<string, unknown>,
): Promise<ApiResponse<WebhookTestResult>> {
  return requestWithMeta<WebhookTestResult>(
    `/v1/webhooks/endpoints/${endpointId}/test`,
    {
      method: "POST",
      body: JSON.stringify({ event_type: eventType, payload }),
    },
    token,
  );
}

export async function fetchWebhookSubscriptions(token: string, endpointId: string): Promise<WebhookSubscription[]> {
  const data = await request<ListResponse<WebhookSubscription>>(
    `/v1/webhooks/subscriptions${buildQuery({ endpoint_id: endpointId })}`,
    {},
    token,
  );
  return normalizeList(data);
}

export async function createWebhookSubscription(
  token: string,
  endpointId: string,
  eventType: string,
  enabled: boolean,
  filters?: Record<string, unknown> | null,
): Promise<WebhookSubscription> {
  return request<WebhookSubscription>(
    "/v1/webhooks/subscriptions",
    {
      method: "POST",
      body: JSON.stringify({ endpoint_id: endpointId, event_type: eventType, enabled, filters }),
    },
    token,
  );
}

export async function updateWebhookSubscription(
  token: string,
  subscriptionId: string,
  enabled: boolean,
): Promise<WebhookSubscription> {
  return request<WebhookSubscription>(
    `/v1/webhooks/subscriptions/${subscriptionId}`,
    {
      method: "PATCH",
      body: JSON.stringify({ enabled }),
    },
    token,
  );
}

export async function deleteWebhookSubscription(token: string, subscriptionId: string): Promise<void> {
  await request(`/v1/webhooks/subscriptions/${subscriptionId}`, { method: "DELETE" }, token);
}

export async function fetchWebhookDeliveries(
  token: string,
  params: {
    endpointId: string;
    status?: string;
    from?: string;
    to?: string;
    limit?: number;
    offset?: number;
    eventType?: string;
    eventId?: string;
  },
): Promise<WebhookDelivery[]> {
  const data = await request<ListResponse<WebhookDelivery>>(
    `/v1/webhooks/deliveries${buildQuery({
      endpoint_id: params.endpointId,
      status: params.status,
      from: params.from,
      to: params.to,
      limit: params.limit,
      offset: params.offset,
      event_type: params.eventType,
      event_id: params.eventId,
    })}`,
    {},
    token,
  );
  return normalizeList(data);
}

export async function fetchWebhookDeliveryDetail(token: string, deliveryId: string): Promise<WebhookDeliveryDetail> {
  return request<WebhookDeliveryDetail>(`/v1/webhooks/deliveries/${deliveryId}`, {}, token);
}

export async function retryWebhookDelivery(
  token: string,
  deliveryId: string,
): Promise<ApiResponse<{ delivery_id: string }>> {
  return requestWithMeta<{ delivery_id: string }>(
    `/v1/webhooks/deliveries/${deliveryId}/retry`,
    { method: "POST" },
    token,
  );
}

export async function pauseWebhookEndpoint(
  token: string,
  endpointId: string,
  reason?: string,
): Promise<WebhookEndpoint> {
  return request<WebhookEndpoint>(
    `/v1/webhooks/endpoints/${endpointId}/pause`,
    { method: "POST", body: JSON.stringify({ reason }) },
    token,
  );
}

export async function resumeWebhookEndpoint(token: string, endpointId: string): Promise<WebhookEndpoint> {
  return request<WebhookEndpoint>(`/v1/webhooks/endpoints/${endpointId}/resume`, { method: "POST" }, token);
}

export async function replayWebhookDeliveries(
  token: string,
  endpointId: string,
  payload: WebhookReplayPayload,
): Promise<ApiResponse<WebhookReplayResult>> {
  return requestWithMeta<WebhookReplayResult>(
    `/v1/webhooks/endpoints/${endpointId}/replay`,
    { method: "POST", body: JSON.stringify(payload) },
    token,
  );
}

export async function fetchWebhookSla(
  token: string,
  endpointId: string,
  window = "15m",
): Promise<WebhookSlaStatus> {
  return request<WebhookSlaStatus>(`/v1/webhooks/endpoints/${endpointId}/sla${buildQuery({ window })}`, {}, token);
}

export async function fetchWebhookAlerts(token: string, endpointId: string): Promise<WebhookAlert[]> {
  const data = await request<ListResponse<WebhookAlert>>(`/v1/webhooks/endpoints/${endpointId}/alerts`, {}, token);
  return normalizeList(data);
}
