export interface ReconciliationRequest {
  id: string;
  status: string;
  date_from: string;
  date_to: string;
  note_client?: string | null;
  note_ops?: string | null;
  result_object_key?: string | null;
  result_bucket?: string | null;
  result_hash_sha256?: string | null;
  version?: number | null;
  created_at?: string | null;
  updated_at?: string | null;
  requested_at?: string | null;
  generated_at?: string | null;
  sent_at?: string | null;
  acknowledged_at?: string | null;
  meta?: Record<string, unknown> | null;
}

export interface ReconciliationRequestList {
  items: ReconciliationRequest[];
  total: number;
  limit: number;
  offset: number;
}
