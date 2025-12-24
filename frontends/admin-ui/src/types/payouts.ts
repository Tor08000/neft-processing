export interface PayoutBatchSummary {
  batch_id: string;
  state: string;
  total_amount: number;
  total_qty: number;
  operations_count: number;
  items_count: number;
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
}

export interface PayoutBatchDetail {
  id: string;
  tenant_id: number;
  partner_id: string;
  date_from: string;
  date_to: string;
  state: string;
  total_amount: number;
  total_qty: number;
  operations_count: number;
  created_at: string;
  sent_at?: string | null;
  settled_at?: string | null;
  provider?: string | null;
  external_ref?: string | null;
  items: PayoutBatchItem[];
}

export interface PayoutExportFile {
  export_id: string;
  batch_id: string;
  format: string;
  state: string;
  provider?: string | null;
  external_ref?: string | null;
  object_key: string;
  bucket: string;
  sha256?: string | null;
  size_bytes?: number | null;
  generated_at?: string | null;
  uploaded_at?: string | null;
  error_message?: string | null;
  download_url: string;
}
