import type { AdminTimelineEvent } from "./finance";

export type PayoutState = "DRAFT" | "READY" | "SENT" | "SETTLED" | "FAILED";

export interface PayoutBatchSummary {
  batch_id: string;
  state: PayoutState;
  total_amount: number;
  total_qty: number;
  operations_count: number;
  items_count: number;
}

export interface PayoutBatchListResponse {
  items: PayoutBatchSummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface MarkPayoutPayload {
  provider: string;
  external_ref: string;
}

export interface PayoutBatchItem {
  id: string;
  azs_id?: string | null;
  product_id?: string | null;
  amount_gross: number;
  commission_amount: number;
  amount_net: number;
  qty: number;
  operations_count: number;
  meta?: Record<string, unknown> | null;
}

export interface PayoutBatchDetail {
  id: string;
  tenant_id: number;
  partner_id: string;
  date_from: string;
  date_to: string;
  state: PayoutState;
  total_amount: number;
  total_qty: number;
  operations_count: number;
  created_at: string;
  sent_at?: string | null;
  settled_at?: string | null;
  provider?: string | null;
  external_ref?: string | null;
  meta?: Record<string, unknown> | null;
  items: PayoutBatchItem[];
}

export interface PayoutReconcileResult {
  batch_id: string;
  computed: {
    total_amount: number;
    operations_count: number;
  };
  recorded: {
    total_amount: number;
    operations_count: number;
  };
  diff: {
    amount: number;
    count: number;
  };
  status: "OK" | "MISMATCH";
}

export interface PayoutExportFile {
  export_id: string;
  batch_id: string;
  format: string;
  state: string;
  provider?: string | null;
  external_ref?: string | null;
  bank_format_code?: string | null;
  object_key: string;
  bucket: string;
  sha256?: string | null;
  size_bytes?: number | null;
  generated_at?: string | null;
  uploaded_at?: string | null;
  error_message?: string | null;
  download_url: string;
}

export interface PayoutExportFormatInfo {
  code: string;
  title: string;
}

export interface PayoutQueueItem {
  payout_id: string;
  partner_org: string;
  amount: number | string;
  net_amount?: number | string | null;
  currency: string;
  status: string;
  blockers: string[];
  block_reason?: string | null;
  created_at?: string | null;
  legal_status?: string | null;
  settlement_state?: string | null;
  correlation_id?: string | null;
  correlation_chain?: string[] | null;
}

export interface PayoutQueueListResponse {
  items: PayoutQueueItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface PayoutPolicyInfo {
  min_payout_amount?: number | string | null;
  payout_hold_days?: number | null;
  payout_schedule?: string | null;
}

export interface PayoutTraceItem {
  entity_type: string;
  entity_id: string;
  amount?: number | string | null;
  currency?: string | null;
  created_at?: string | null;
}

export interface PayoutDetail extends PayoutQueueItem {
  processed_at?: string | null;
  policy?: PayoutPolicyInfo | null;
  trace?: PayoutTraceItem[];
  totals?: Record<string, number | string> | null;
  settlement_snapshot?: Record<string, unknown> | null;
  block_reason_tree?: Record<string, unknown> | string[] | null;
  correlation_chain?: string[] | null;
  audit_events?: AdminTimelineEvent[] | null;
}
