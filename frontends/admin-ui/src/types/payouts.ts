export type PayoutState = "READY" | "SENT" | "SETTLED" | "FAILED" | "DRAFT";

export interface PayoutBatch {
  id: string;
  partner_id: string;
  date_from: string;
  date_to: string;
  state: PayoutState;
  total_amount: number;
  total_qty: number;
  operations_count: number;
  provider?: string | null;
  external_ref?: string | null;
  created_at?: string | null;
  sent_at?: string | null;
  settled_at?: string | null;
}

export interface PayoutBatchItem {
  id: string;
  azs_id?: string | null;
  product?: string | null;
  qty: number;
  amount_gross: number;
  commission: number;
  amount_net: number;
  operations_count?: number | null;
}

export interface PayoutBatchDetails {
  batch: PayoutBatch;
  items: PayoutBatchItem[];
}

export interface PayoutBatchesResponse {
  items: PayoutBatch[];
  total: number;
  limit: number;
  offset: number;
}

export interface PayoutReconcileResult {
  status: "OK" | "MISMATCH";
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
}

export interface PayoutBatchesQuery {
  tenant_id?: string;
  partner_id?: string;
  state?: PayoutState[];
  date_from?: string;
  date_to?: string;
  limit?: number;
  offset?: number;
  sort?: string;
}

export interface MarkPayoutPayload {
  provider: string;
  external_ref: string;
}
