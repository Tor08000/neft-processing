export interface AccountingExportItem {
  id?: string;
  type?: string;
  title?: string;
  period_from?: string | null;
  period_to?: string | null;
  checksum?: string | null;
  mapping_version?: string | null;
  status?: string | null;
  erp_status?: string | null;
  reconciliation_status?: string | null;
  download_url?: string | null;
  created_at?: string | null;
  reconciliation_verdict?: string | null;
}

export interface AccountingExportList {
  items: AccountingExportItem[];
}

export interface ExportTimelineEvent {
  status: string;
  occurred_at: string;
  message?: string | null;
}

export interface ExportReconciliationSummary {
  expected_total?: number | null;
  received_total?: number | null;
  mismatch_summary?: string | null;
}

export interface AccountingExportDetails extends AccountingExportItem {
  line_count?: number | null;
  totals?: Record<string, number> | null;
  erp_timeline?: ExportTimelineEvent[] | null;
  reconciliation?: ExportReconciliationSummary | null;
}
