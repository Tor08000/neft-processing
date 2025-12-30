export type PriceVersionStatus = "DRAFT" | "VALIDATED" | "PUBLISHED" | "ARCHIVED";

export type PriceStationScope = "all" | "list";

export interface PriceVersion {
  id: string;
  partner_id: string;
  station_scope: PriceStationScope;
  station_ids?: string[] | null;
  status: PriceVersionStatus;
  created_at: string;
  updated_at?: string | null;
  created_by?: string | null;
  publish_at?: string | null;
  active: boolean;
  item_count: number;
  error_count: number;
  checksum_sha256?: string | null;
  meta?: Record<string, string | number | boolean | null> | null;
}

export interface PriceItemError {
  code: string;
  message: string;
}

export interface PriceItem {
  station_id?: string | null;
  station_code?: string | null;
  product_code: string;
  price: number;
  currency: string;
  valid_from: string;
  valid_to?: string | null;
  vat?: number | null;
  errors?: PriceItemError[] | null;
}

export interface ValidationResult {
  ok: boolean;
  errors_total: number;
  warnings_total: number;
  sample_errors?: PriceItemError[] | null;
  recommended_actions?: string[] | null;
}

export interface DiffResult {
  added_count: number;
  removed_count: number;
  changed_count: number;
  changed_fields?: Record<string, number> | null;
  sample_changed?: Array<{
    station_id?: string | null;
    station_code?: string | null;
    product_code: string;
    before: Partial<PriceItem> | null;
    after: Partial<PriceItem> | null;
  }> | null;
  summary?: string | null;
}

export interface PriceAuditEvent {
  id: string;
  action: "created" | "imported" | "validated" | "published" | "rollback";
  actor?: string | null;
  created_at: string;
  details?: Record<string, string | number | boolean | null> | null;
  correlation_id?: string | null;
}

export interface PriceVersionsResponse {
  items: PriceVersion[];
}

export interface PriceItemsResponse {
  items: PriceItem[];
  total?: number | null;
}

export interface PriceAuditResponse {
  items: PriceAuditEvent[];
}

export interface PriceImportResult {
  rows_parsed: number;
  errors_found: number;
  sample_errors?: PriceItemError[] | null;
}

export interface PriceAnalyticsVersion {
  price_version_id: string;
  published_at: string | null;
  orders_count: number;
  revenue_total: number;
  avg_order_value: number;
  refunds_count: number;
}

export interface PriceAnalyticsOffer {
  offer_id: string;
  orders_count: number;
  conversion_rate: number | null;
  avg_price: number;
  revenue_total: number;
}

export interface PriceAnalyticsInsight {
  type: string;
  severity: "INFO" | "WARN" | "ERROR" | string;
  message: string;
  price_version_id?: string | null;
}

export interface PriceAnalyticsSeriesPoint {
  date: string;
  orders_count: number;
  revenue_total: number;
}
