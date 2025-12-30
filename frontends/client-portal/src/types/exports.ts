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
}

export interface AccountingExportList {
  items: AccountingExportItem[];
}
