export type BankStubPaymentStatus = "CREATED" | "POSTED" | "SETTLED" | "REVERSED";

export type BankStubPayment = {
  id: string;
  tenant_id: number;
  invoice_id: string;
  payment_ref: string;
  amount: number;
  currency: string;
  status: BankStubPaymentStatus;
  idempotency_key: string;
  created_at: string;
  updated_at: string;
};

export type BankStubStatementLine = {
  payment_ref: string;
  invoice_number?: string | null;
  amount: number;
  currency: string;
  posted_at: string;
  meta?: Record<string, unknown> | null;
};

export type BankStubStatement = {
  id: string;
  tenant_id: number;
  period_from: string;
  period_to: string;
  checksum: string;
  payload?: Record<string, unknown> | null;
  created_at: string;
  lines: BankStubStatementLine[];
};

export type ErpStubExportStatus = "CREATED" | "SENT" | "ACKED" | "FAILED";
export type ErpStubExportType = "INVOICES" | "PAYMENTS" | "SETTLEMENT" | "RECONCILIATION";

export type ErpStubExportItem = {
  entity_type: string;
  entity_id: string;
  snapshot_json: Record<string, unknown>;
  created_at: string;
};

export type ErpStubExport = {
  id: string;
  tenant_id: number;
  export_ref: string;
  export_type: ErpStubExportType;
  payload_hash: string;
  status: ErpStubExportStatus;
  created_at: string;
  updated_at: string;
  items: ErpStubExportItem[];
};
