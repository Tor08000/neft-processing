export interface ReconciliationImport {
  id: string;
  uploaded_by_admin?: string | null;
  uploaded_at: string;
  file_object_key: string;
  format: string;
  period_from?: string | null;
  period_to?: string | null;
  status: string;
  error?: string | null;
}

export interface ReconciliationImportListResponse {
  items: ReconciliationImport[];
}

export interface ReconciliationTransaction {
  id: string;
  import_id: string;
  bank_tx_id: string;
  posted_at: string;
  amount: number | string;
  currency: string;
  payer_name?: string | null;
  payer_inn?: string | null;
  reference?: string | null;
  purpose_text?: string | null;
  raw_json?: Record<string, unknown> | null;
  matched_status: string;
  matched_invoice_id?: string | null;
  confidence_score: number | string;
  created_at: string;
}

export interface ReconciliationTransactionListResponse {
  items: ReconciliationTransaction[];
}
