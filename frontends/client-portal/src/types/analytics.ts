export interface AnalyticsAttentionItem {
  id: string;
  title: string;
  description?: string | null;
  href: string;
  severity?: "info" | "warning" | "critical" | null;
}

export interface AnalyticsSeriesPoint {
  date: string;
  value: number;
}

export interface AnalyticsDailyMetricsResponse {
  from: string;
  to: string;
  currency?: string | null;
  spend: {
    total: number;
    series: AnalyticsSeriesPoint[];
  };
  orders: {
    total: number;
    completed: number;
    refunds: number;
    series: AnalyticsSeriesPoint[];
  };
  declines: {
    total: number;
    top_reason?: string | null;
    series: AnalyticsSeriesPoint[];
  };
  documents: {
    attention: number;
  };
  exports: {
    attention: number;
  };
  attention: AnalyticsAttentionItem[];
}

export interface AnalyticsSpendSummaryResponse {
  currency?: string | null;
  total_spend: number;
  avg_daily_spend?: number;
  trend: AnalyticsSeriesPoint[];
  top_stations: Array<{ name: string; amount: number }>;
  top_merchants: Array<{ name: string; amount: number }>;
  top_cards: Array<{ name: string; amount: number }>;
  top_drivers: Array<{ name: string; amount: number }>;
  product_breakdown: Array<{ product: string; amount: number }>;
  export_available?: boolean;
  export_dataset?: string | null;
}

export interface AnalyticsDeclinesResponse {
  total: number;
  top_reasons: Array<{ reason: string; count: number }>;
  trend: Array<{ date: string; reason: string; count: number }>;
  heatmap?: Array<{ station: string; reason: string; count: number }>;
  expensive: Array<{ id: string; reason: string; amount: number; station?: string | null }>;
}

export interface AnalyticsOrdersSummaryResponse {
  total: number;
  completed: number;
  cancelled: number;
  refunds_rate: number;
  refunds_count: number;
  avg_order_value: number;
  top_services: Array<{ name: string; orders: number }>;
  status_breakdown: Array<{ status: string; count: number }>;
}

export interface AnalyticsDocumentsSummaryResponse {
  issued: number;
  signed: number;
  edo_pending: number;
  edo_failed: number;
  attention: Array<{ id: string; title: string; status: string }>;
}

export interface AnalyticsExportsSummaryResponse {
  total: number;
  ok: number;
  mismatch: number;
  items: Array<{
    id: string;
    status: string;
    checksum?: string | null;
    mapping_version?: string | null;
    created_at: string;
  }>;
}

export interface AnalyticsExportRequest {
  dataset: string;
  from: string;
  to: string;
}

export interface AnalyticsExportResponse {
  id: string;
  status: string;
  download_url?: string | null;
}
