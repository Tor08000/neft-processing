export type RuntimeHealthStatus = "UP" | "DEGRADED" | "DOWN";

export interface RuntimeHealthSummary {
  core_api: RuntimeHealthStatus;
  auth_host: RuntimeHealthStatus;
  gateway: RuntimeHealthStatus;
  postgres: RuntimeHealthStatus;
  redis: RuntimeHealthStatus;
  minio: RuntimeHealthStatus;
  clickhouse: RuntimeHealthStatus;
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
}

export interface RuntimeMoneyRisk {
  payouts_blocked: number;
  settlements_pending: number;
  overdue_clients: number;
}

export interface RuntimeCriticalEvent {
  ts: string;
  kind: string;
  message: string;
  correlation_id?: string | null;
}

export interface RuntimeEvents {
  critical_last_10: RuntimeCriticalEvent[];
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
}
