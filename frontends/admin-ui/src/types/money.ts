export interface MoneyHealthResponse {
  orphan_ledger_transactions?: number | null;
  missing_ledger_postings?: number | null;
  invariant_violations?: number | null;
  stuck_authorized?: number | null;
  stuck_pending_settlement?: number | null;
  cross_period_anomalies?: number | null;
  missing_snapshots?: number | null;
  broken_chains?: number | null;
  top_offenders?: MoneyHealthOffender[] | null;
  [key: string]: unknown;
}

export interface MoneyHealthOffender {
  id?: string | null;
  flow_type?: string | null;
  flow_ref_id?: string | null;
  issue?: string | null;
  details?: string | null;
}

export interface MoneyReplayResponse {
  summary?: Record<string, unknown> | null;
  mismatches?: unknown[] | null;
  recommended_actions?: string | null;
  [key: string]: unknown;
}

export interface MoneyExplainResponse {
  totals?: Record<string, unknown> | null;
  segments?: unknown[] | null;
  charges?: unknown[] | null;
  invoice_ids?: string[] | null;
  ledger_summary?: Record<string, unknown> | null;
  money_flow_links?: unknown[] | null;
  snapshots?: Record<string, unknown> | null;
  replay_status?: Record<string, unknown> | null;
  [key: string]: unknown;
}
