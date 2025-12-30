export type WebhookEndpointStatus = "ACTIVE" | "DISABLED";

export interface WebhookEndpoint {
  id: string;
  owner_type?: string;
  owner_id?: string;
  url: string;
  status: WebhookEndpointStatus;
  signing_algo?: string | null;
  delivery_paused?: boolean;
  paused_at?: string | null;
  paused_reason?: string | null;
  created_at: string;
}

export interface WebhookEndpointCreatePayload {
  owner_type: "PARTNER";
  owner_id: string;
  url: string;
  signing_algo: "HMAC_SHA256";
  enabled?: boolean;
}

export interface WebhookEndpointCreateResponse {
  endpoint?: WebhookEndpoint;
  endpoint_id?: string;
  id?: string;
  secret: string;
  headers?: Record<string, string>;
}

export interface WebhookEndpointSecretResponse {
  endpoint_id?: string;
  id?: string;
  secret: string;
}

export interface WebhookSubscription {
  id: string;
  endpoint_id: string;
  event_type: string;
  enabled: boolean;
  filters?: Record<string, unknown> | null;
}

export type WebhookDeliveryStatus = "DELIVERED" | "FAILED" | "DEAD" | "PENDING" | "PAUSED";

export interface WebhookDelivery {
  id: string;
  endpoint_id: string;
  event_type: string;
  status: WebhookDeliveryStatus;
  attempt?: number | null;
  last_http_status?: number | null;
  latency_ms?: number | null;
  occurred_at: string;
  event_id?: string | null;
}

export interface WebhookSlaStatus {
  window: string;
  success_ratio: number;
  avg_latency_ms?: number | null;
  sla_breaches: number;
}

export interface WebhookAlert {
  id: string;
  type: "DELIVERY_FAILURE" | "SLA_BREACH" | "PAUSED_TOO_LONG";
  window: string;
  created_at: string;
}

export interface WebhookReplayPayload {
  from: string;
  to: string;
  event_types?: string[];
  only_failed?: boolean;
}

export interface WebhookReplayResult {
  replay_id: string;
  scheduled_deliveries: number;
}

export interface WebhookDeliveryAttempt {
  attempt: number;
  http_status?: number | null;
  error?: string | null;
  latency_ms?: number | null;
  delivered_at?: string | null;
  next_retry_at?: string | null;
  correlation_id?: string | null;
}

export interface WebhookDeliveryDetail extends WebhookDelivery {
  endpoint_url?: string | null;
  envelope?: Record<string, unknown> | null;
  headers?: Record<string, string> | null;
  attempts?: WebhookDeliveryAttempt[] | null;
  error?: string | null;
  correlation_id?: string | null;
}

export interface WebhookTestResult {
  delivery_id: string;
  http_status?: number | null;
  latency_ms?: number | null;
  error?: string | null;
}
