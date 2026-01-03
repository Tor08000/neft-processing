import { apiGet, apiPost } from "./client";
import type {
  BankStubPayment,
  BankStubStatement,
  ErpStubExport,
  ErpStubExportType,
} from "../types/stubs";

const BANK_STUB_BASE = "/api/core/v1/admin/bank_stub";
const ERP_STUB_BASE = "/api/core/v1/admin/erp_stub";

export async function createBankStubPayment(payload: {
  invoice_id: string;
  amount?: number | null;
  idempotency_key?: string | null;
}): Promise<BankStubPayment> {
  return apiPost(`${BANK_STUB_BASE}/payments`, payload);
}

export async function getBankStubPayment(paymentId: string): Promise<BankStubPayment> {
  return apiGet(`${BANK_STUB_BASE}/payments/${paymentId}`);
}

export async function generateBankStubStatement(params: { from: string; to: string }): Promise<BankStubStatement> {
  const query = new URLSearchParams({ from: params.from, to: params.to }).toString();
  return apiPost(`${BANK_STUB_BASE}/statements/generate?${query}`);
}

export async function getBankStubStatement(statementId: string): Promise<BankStubStatement> {
  return apiGet(`${BANK_STUB_BASE}/statements/${statementId}`);
}

export async function createErpStubExport(payload: {
  export_type: ErpStubExportType;
  entity_ids?: string[];
  period_from?: string | null;
  period_to?: string | null;
  export_ref?: string | null;
}): Promise<ErpStubExport> {
  return apiPost(`${ERP_STUB_BASE}/exports`, payload);
}

export async function getErpStubExport(exportId: string): Promise<ErpStubExport> {
  return apiGet(`${ERP_STUB_BASE}/exports/${exportId}`);
}

export async function ackErpStubExport(exportId: string): Promise<ErpStubExport> {
  return apiPost(`${ERP_STUB_BASE}/exports/${exportId}/ack`);
}
