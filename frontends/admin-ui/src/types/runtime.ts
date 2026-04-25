export type RuntimeHealthStatus = "UP" | "DEGRADED" | "DOWN";

export interface RuntimeHealthSummary {
  core_api: RuntimeHealthStatus;
  auth_host: RuntimeHealthStatus;
  gateway: RuntimeHealthStatus;
  integration_hub: RuntimeHealthStatus;
  document_service: RuntimeHealthStatus;
  logistics_service: RuntimeHealthStatus;
  ai_service: RuntimeHealthStatus;
  postgres: RuntimeHealthStatus;
  redis: RuntimeHealthStatus;
  minio: RuntimeHealthStatus;
  clickhouse: RuntimeHealthStatus;
  prometheus: RuntimeHealthStatus;
  grafana: RuntimeHealthStatus;
  loki: RuntimeHealthStatus;
  otel_collector: RuntimeHealthStatus;
}

export interface RuntimeQueueState {
  depth: number;
  oldest_age_sec: number;
}

export interface RuntimeQueueCount {
  count: number;
}

export interface RuntimeQueues {
  settlement: RuntimeQueueState;
  payout: RuntimeQueueState;
  blocked_payouts: RuntimeQueueCount;
  payment_intakes_pending: RuntimeQueueCount;
}

export interface RuntimeViolationTop {
  count: number;
  top: string[];
}

export interface RuntimeViolations {
  immutable: RuntimeViolationTop;
  invariants: RuntimeViolationTop;
  sla_penalties: RuntimeViolationTop;
}

export interface RuntimeMoneyRisk {
  payouts_blocked: number;
  settlements_pending: number;
  overdue_clients: number;
}

export type CriticalEvent = {
  ts: string;
  kind: string;
  message: string;
  correlation_id?: string;
};

export interface RuntimeEvents {
  critical_last_10: CriticalEvent[];
}

export type ExternalProviderStatus =
  | "DISABLED"
  | "CONFIGURED"
  | "HEALTHY"
  | "DEGRADED"
  | "AUTH_FAILED"
  | "TIMEOUT"
  | "UNSUPPORTED"
  | "RATE_LIMITED";

export interface ExternalProviderHealth {
  service: string;
  provider: string;
  mode: string;
  status: ExternalProviderStatus;
  configured: boolean;
  last_success_at?: string | null;
  last_error_code?: string | null;
  message?: string | null;
}

export interface RuntimeSummary {
  ts: string;
  environment: string;
  read_only: boolean;
  health: RuntimeHealthSummary;
  queues: RuntimeQueues;
  violations: RuntimeViolations;
  money_risk: RuntimeMoneyRisk;
  events: RuntimeEvents;
  warnings: string[];
  missing_tables: string[];
  external_providers: ExternalProviderHealth[];
}
