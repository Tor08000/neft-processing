export type OpsSignalStatus = "GREEN" | "YELLOW" | "RED";

export interface OpsEnvSummary {
  name: string;
  build: string;
}

export interface OpsTimeSummary {
  now: string;
}

export interface OpsCoreSummary {
  health: string;
}

export interface OpsExportQueueSummary {
  queued: number;
  running: number;
  failed_1h: number;
}

export interface OpsPayoutQueueSummary {
  queued: number;
  blocked: number;
}

export interface OpsSettlementQueueSummary {
  queued: number;
  finalizing: number;
}

export interface OpsEmailQueueSummary {
  queued: number;
  failed_1h: number;
}

export interface OpsHelpdeskQueueSummary {
  queued: number;
  failed_1h: number;
}

export interface OpsQueuesSummary {
  exports: OpsExportQueueSummary;
  payouts: OpsPayoutQueueSummary;
  settlements: OpsSettlementQueueSummary;
  emails: OpsEmailQueueSummary;
  helpdesk_outbox: OpsHelpdeskQueueSummary;
}

export interface OpsMorTopReason {
  reason: string;
  count: number;
}

export interface OpsMorSummary {
  immutable_violations_24h: number;
  payout_blocked_total_24h: number;
  payout_blocked_top_reasons: OpsMorTopReason[];
  clawback_required_24h: number;
  admin_overrides_24h: number;
}

export interface OpsBillingSummary {
  overdue_orgs: number;
  overdue_amount: number;
  dunning_sent_24h: number;
  auto_suspends_24h: number;
}

export interface OpsReconciliationSummary {
  imports_24h: number;
  parse_failed_24h: number;
  unmatched_24h: number;
  auto_approved_24h: number;
}

export interface OpsExportsSummary {
  jobs_24h: number;
  failed_24h: number;
  avg_duration_sec: number;
}

export interface OpsSupportSummary {
  open_tickets: number;
  sla_breaches_24h: number;
}

export interface OpsSignalsSummary {
  status: OpsSignalStatus;
  reasons: string[];
}

export interface OpsSummaryResponse {
  env: OpsEnvSummary;
  time: OpsTimeSummary;
  core: OpsCoreSummary;
  queues: OpsQueuesSummary;
  mor: OpsMorSummary;
  billing: OpsBillingSummary;
  reconciliation: OpsReconciliationSummary;
  exports: OpsExportsSummary;
  support: OpsSupportSummary;
  signals: OpsSignalsSummary;
}

export interface OpsBlockedPayoutItem {
  id: string;
  settlement_id: string;
  status: string;
  amount: number;
  currency: string;
  created_at: string;
  error?: string | null;
}

export interface OpsFailedExportItem {
  id: string;
  report_type: string;
  format: string;
  status: string;
  created_at: string;
  error_message?: string | null;
}

export interface OpsFailedReconciliationImport {
  id: string;
  status: string;
  uploaded_at: string;
  error?: string | null;
}

export interface OpsSupportBreachItem {
  id: string;
  status: string;
  priority: string;
  created_at: string;
  sla_first_response_status: string;
  sla_resolution_status: string;
}

export interface OpsBlockedPayoutsResponse {
  items: OpsBlockedPayoutItem[];
}

export interface OpsFailedExportsResponse {
  items: OpsFailedExportItem[];
}

export interface OpsFailedImportsResponse {
  items: OpsFailedReconciliationImport[];
}

export interface OpsSupportBreachesResponse {
  items: OpsSupportBreachItem[];
}
