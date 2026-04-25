import { apiDownload, apiGet, apiPost } from "./client";
import type {
  ReconciliationImport,
  ReconciliationImportListResponse,
  ReconciliationTransactionListResponse,
} from "../types/reconciliationImports";

export type ReconciliationScope = "internal" | "external" | "unknown";
export type ReconciliationRunStatus = "completed" | "failed" | "started" | "running" | "unknown";
export type ReconciliationDiscrepancyStatus = "open" | "resolved" | "ignored" | "unknown";
export type ReconciliationRunExportScope = "full" | "discrepancies";
export type ReconciliationFixtureScenario = "SCN2_WRONG_AMOUNT" | "SCN2_UNMATCHED" | "SCN3_DOUBLE_PAYMENT";
export type ReconciliationFixtureFormat = "CSV" | "CLIENT_BANK_1C" | "MT940" | "ALL";
export type ReconciliationFixtureWrongAmountMode = "LESS" | "MORE";

export interface ReconciliationRun {
  id: string;
  scope: ReconciliationScope;
  provider?: string | null;
  period_start: string;
  period_end: string;
  status: ReconciliationRunStatus;
  created_at: string;
  created_by_user_id?: string | null;
  summary?: Record<string, unknown> | null;
  audit_event_id?: string | null;
  statement?: ReconciliationStatementSummary | null;
  timeline?: ReconciliationAuditEvent[];
  link_counts?: ReconciliationLinkCounts | null;
}

export interface ReconciliationRunListResponse {
  runs: ReconciliationRun[];
  unavailable?: boolean;
}

export interface ReconciliationRunResult {
  run: ReconciliationRun | null;
  unavailable?: boolean;
}

export interface ReconciliationDiscrepancy {
  id: string;
  run_id: string;
  ledger_account_id?: string | null;
  currency: string;
  discrepancy_type: string;
  internal_amount?: number | string | null;
  external_amount?: number | string | null;
  delta?: number | string | null;
  details?: Record<string, unknown> | null;
  status: ReconciliationDiscrepancyStatus;
  resolution?: Record<string, unknown> | null;
  created_at: string;
  timeline?: ReconciliationAuditEvent[];
  adjustment_explain?: ReconciliationAdjustmentExplain | null;
}

export interface ReconciliationDiscrepancyListResponse {
  discrepancies: ReconciliationDiscrepancy[];
  unavailable?: boolean;
}

export interface ReconciliationAuditEvent {
  ts: string;
  event_type: string;
  entity_type: string;
  entity_id: string;
  action: string;
  reason?: string | null;
  actor_id?: string | null;
  actor_email?: string | null;
  before?: Record<string, unknown> | null;
  after?: Record<string, unknown> | null;
}

export interface ReconciliationLinkCounts {
  matched: number;
  mismatched: number;
  pending: number;
}

export interface ReconciliationStatementSummary {
  id: string;
  provider: string;
  period_start: string;
  period_end: string;
  currency: string;
  total_in?: number | string | null;
  total_out?: number | string | null;
  closing_balance?: number | string | null;
  created_at: string;
  source_hash: string;
  audit_event_id?: string | null;
}

export interface ReconciliationStatementTotalCheck {
  kind: string;
  status: string;
  external_amount?: number | string | null;
  internal_amount?: number | string | null;
  delta?: number | string | null;
  discrepancy_id?: string | null;
  discrepancy_status?: ReconciliationDiscrepancyStatus | null;
}

export interface ExternalStatementExplain {
  related_run_id?: string | null;
  related_run_status?: ReconciliationRunStatus | null;
  relation_source?: string | null;
  line_count: number;
  matched_links: number;
  mismatched_links: number;
  pending_links: number;
  unmatched_external: number;
  unmatched_internal: number;
  mismatched_amount: number;
  open_discrepancies: number;
  resolved_discrepancies: number;
  ignored_discrepancies: number;
  adjusted_discrepancies: number;
  total_checks: ReconciliationStatementTotalCheck[];
}

export interface ReconciliationLink {
  id: string;
  run_id?: string | null;
  entity_type: string;
  entity_id: string;
  provider: string;
  currency: string;
  expected_amount: number | string;
  direction: string;
  expected_at: string;
  match_key?: string | null;
  status: string;
  created_at: string;
  discrepancy_ids: string[];
  review_status?: ReconciliationDiscrepancyStatus | null;
}

export interface ReconciliationLinkListResponse {
  links: ReconciliationLink[];
  unavailable?: boolean;
}

export interface ReconciliationAdjustmentPosting {
  account_id: string;
  account_type: string;
  client_id?: string | null;
  direction: string;
  amount: number;
  currency: string;
  entry_hash: string;
}

export interface ReconciliationAdjustmentExplain {
  adjustment_tx_id: string;
  transaction_type?: string | null;
  external_ref_type?: string | null;
  external_ref_id?: string | null;
  tenant_id?: number | null;
  currency?: string | null;
  total_amount?: number | null;
  posted_at?: string | null;
  meta?: Record<string, unknown> | null;
  entries: ReconciliationAdjustmentPosting[];
  audit_events: ReconciliationAuditEvent[];
}

export interface ExternalStatement {
  id: string;
  provider: string;
  period_start: string;
  period_end: string;
  currency: string;
  total_in?: number | string | null;
  total_out?: number | string | null;
  closing_balance?: number | string | null;
  lines?: Record<string, unknown>[] | null;
  created_at: string;
  source_hash: string;
  audit_event_id?: string | null;
  explain?: ExternalStatementExplain | null;
  timeline?: ReconciliationAuditEvent[];
}

export interface ExternalStatementListResponse {
  statements: ExternalStatement[];
  unavailable?: boolean;
}

export interface ExternalStatementResult {
  statement: ExternalStatement | null;
  unavailable?: boolean;
}

export interface ReconciliationFixtureFile {
  format: "CSV" | "CLIENT_BANK_1C" | "MT940";
  file_name: string;
  download_url: string;
}

export interface ReconciliationFixtureBundle {
  bundle_id: string;
  files: ReconciliationFixtureFile[];
  notes: string;
  unavailable?: boolean;
}

export interface ReconciliationFixtureImportResult {
  import_id: string;
  object_key: string;
  unavailable?: boolean;
}

export interface ReconciliationImportCompleteResult {
  id: string;
  status: string;
  unavailable?: boolean;
}

export interface ResolveDiscrepancyResult {
  adjustment_tx_id?: string;
  unavailable?: boolean;
}

export interface ReconciliationRunExport {
  exported_at: string;
  run: ReconciliationRun;
  discrepancies: ReconciliationDiscrepancy[];
  links: ReconciliationLink[];
  unavailable?: boolean;
}

export interface ReconciliationDiscrepancyResult {
  discrepancy: ReconciliationDiscrepancy | null;
  unavailable?: boolean;
}

export interface ReconciliationRunExportDownload {
  blob: Blob;
  fileName: string | null;
  contentType: string | null;
  unavailable?: boolean;
}

export type ReconciliationRunExportOptions = {
  export_scope?: ReconciliationRunExportScope;
  discrepancy_status?: Exclude<ReconciliationDiscrepancyStatus, "unknown"> | "";
  discrepancy_type?: string;
};

export interface IgnoreDiscrepancyResult {
  status?: string;
  unavailable?: boolean;
}

export class NotAvailableError extends Error {
  constructor(message = "Not available in this environment") {
    super(message);
    this.name = "NotAvailableError";
  }
}

const isNotAvailableMessage = (message?: string) => Boolean(message && /HTTP (404|501)\b/.test(message));

export const isNotAvailableError = (error: unknown): boolean => {
  if (error instanceof NotAvailableError) return true;
  if (error instanceof Error) {
    return isNotAvailableMessage(error.message);
  }
  return false;
};

const handleAvailability = <T>(error: unknown, fallback: T): T => {
  if (isNotAvailableError(error)) {
    return fallback;
  }
  if (error instanceof Error && isNotAvailableMessage(error.message)) {
    return fallback;
  }
  throw error;
};

export const listRuns = async (params?: {
  scope?: string;
  provider?: string;
  status?: string;
}): Promise<ReconciliationRunListResponse> => {
  try {
    const response = await apiGet<{ runs: ReconciliationRun[] }>("/reconciliation/runs", params);
    return { runs: response.runs ?? [] };
  } catch (error) {
    return handleAvailability(error, { runs: [], unavailable: true });
  }
};

export const listImports = async (): Promise<ReconciliationImportListResponse> =>
  apiGet("/reconciliation/imports");

export const getImport = async (importId: string): Promise<ReconciliationImport> =>
  apiGet(`/reconciliation/imports/${importId}`);

export const listImportTransactions = async (params: {
  import_id?: string;
  status?: string;
}): Promise<ReconciliationTransactionListResponse> =>
  apiGet("/reconciliation/transactions", params);

export const parseImport = async (importId: string, payload: { reason: string; correlation_id: string }) =>
  apiPost(`/reconciliation/imports/${importId}/parse`, payload);

export const matchImport = async (importId: string, payload: { reason: string; correlation_id: string }) =>
  apiPost(`/reconciliation/imports/${importId}/match`, payload);

export const applyImportTransaction = async (
  transactionId: string,
  payload: { invoice_id: string; reason: string; correlation_id: string },
) => apiPost(`/reconciliation/transactions/${transactionId}/apply`, payload);

export const ignoreImportTransaction = async (
  transactionId: string,
  payload: { reason: string; correlation_id: string },
) => apiPost(`/reconciliation/transactions/${transactionId}/ignore`, payload);

export const createInternalRun = async (payload: {
  period_start: string;
  period_end: string;
}): Promise<ReconciliationRunResult> => {
  try {
    const run = await apiPost<ReconciliationRun>("/reconciliation/internal", payload);
    return { run };
  } catch (error) {
    return handleAvailability(error, { run: null, unavailable: true });
  }
};

export const createExternalRun = async (payload: { statement_id: string }): Promise<ReconciliationRunResult> => {
  try {
    const run = await apiPost<ReconciliationRun>("/reconciliation/external/run", payload);
    return { run };
  } catch (error) {
    return handleAvailability(error, { run: null, unavailable: true });
  }
};

export const getRun = async (runId: string): Promise<ReconciliationRunResult> => {
  try {
    const run = await apiGet<ReconciliationRun>(`/reconciliation/runs/${runId}`);
    return { run };
  } catch (error) {
    return handleAvailability(error, { run: null, unavailable: true });
  }
};

export const listRunLinks = async (
  runId: string,
  params?: { status?: string },
): Promise<ReconciliationLinkListResponse> => {
  try {
    const response = await apiGet<{ links: ReconciliationLink[] }>(`/reconciliation/runs/${runId}/links`, params);
    return { links: response.links ?? [] };
  } catch (error) {
    return handleAvailability(error, { links: [], unavailable: true });
  }
};

export const downloadRunExport = async (
  runId: string,
  format: "json" | "csv",
  options?: ReconciliationRunExportOptions,
): Promise<ReconciliationRunExportDownload> => {
  try {
    return await apiDownload(
      `/reconciliation/runs/${runId}/export`,
      {
        format,
        export_scope: options?.export_scope,
        discrepancy_status: options?.discrepancy_status || undefined,
        discrepancy_type: options?.discrepancy_type || undefined,
      },
      format === "csv" ? "text/csv" : "application/json",
    );
  } catch (error) {
    return handleAvailability(error, {
      blob: new Blob([]),
      fileName: null,
      contentType: null,
      unavailable: true,
    });
  }
};

export const listDiscrepancies = async (
  runId: string,
  params?: { status?: string },
): Promise<ReconciliationDiscrepancyListResponse> => {
  try {
    const response = await apiGet<{ discrepancies: ReconciliationDiscrepancy[] }>(
      `/reconciliation/runs/${runId}/discrepancies`,
      params,
    );
    return { discrepancies: response.discrepancies ?? [] };
  } catch (error) {
    return handleAvailability(error, { discrepancies: [], unavailable: true });
  }
};

export const getDiscrepancy = async (discrepancyId: string): Promise<ReconciliationDiscrepancyResult> => {
  try {
    const response = await apiGet<{ discrepancy: ReconciliationDiscrepancy }>(`/reconciliation/discrepancies/${discrepancyId}`);
    return { discrepancy: response.discrepancy };
  } catch (error) {
    return handleAvailability(error, { discrepancy: null, unavailable: true });
  }
};

export const listStatementDiscrepancies = async (
  statementId: string,
  params?: { status?: Exclude<ReconciliationDiscrepancyStatus, "unknown"> | ""; discrepancy_type?: string },
): Promise<ReconciliationDiscrepancyListResponse> => {
  try {
    const response = await apiGet<{ discrepancies: ReconciliationDiscrepancy[] }>(
      `/reconciliation/external/statements/${statementId}/discrepancies`,
      params,
    );
    return { discrepancies: response.discrepancies ?? [] };
  } catch (error) {
    return handleAvailability(error, { discrepancies: [], unavailable: true });
  }
};

export const resolveDiscrepancy = async (
  discrepancyId: string,
  payload: { note: string },
): Promise<ResolveDiscrepancyResult> => {
  try {
    return await apiPost<ResolveDiscrepancyResult>(
      `/reconciliation/discrepancies/${discrepancyId}/resolve-adjustment`,
      payload,
    );
  } catch (error) {
    return handleAvailability(error, { unavailable: true });
  }
};

export const ignoreDiscrepancy = async (
  discrepancyId: string,
  payload: { reason: string },
): Promise<IgnoreDiscrepancyResult> => {
  try {
    return await apiPost<IgnoreDiscrepancyResult>(
      `/reconciliation/discrepancies/${discrepancyId}/ignore`,
      payload,
    );
  } catch (error) {
    return handleAvailability(error, { unavailable: true });
  }
};

export const uploadStatement = async (payload: {
  provider: string;
  period_start: string;
  period_end: string;
  currency: string;
  totals?: { total_in?: number | null; total_out?: number | null; closing_balance?: number | null };
  lines?: Record<string, unknown>[] | null;
}): Promise<ExternalStatementResult> => {
  try {
    const response = await apiPost<ExternalStatement>("/reconciliation/external/statements", {
      provider: payload.provider,
      period_start: payload.period_start,
      period_end: payload.period_end,
      currency: payload.currency,
      total_in: payload.totals?.total_in ?? null,
      total_out: payload.totals?.total_out ?? null,
      closing_balance: payload.totals?.closing_balance ?? null,
      lines: payload.lines ?? null,
    });
    return { statement: response };
  } catch (error) {
    return handleAvailability(error, { statement: null, unavailable: true });
  }
};

export const listStatements = async (params?: { provider?: string }): Promise<ExternalStatementListResponse> => {
  try {
    const response = await apiGet<{ statements: ExternalStatement[] }>(
      "/reconciliation/external/statements",
      params,
    );
    return { statements: response.statements ?? [] };
  } catch (error) {
    return handleAvailability(error, { statements: [], unavailable: true });
  }
};

export const getStatement = async (statementId: string): Promise<ExternalStatementResult> => {
  try {
    const statement = await apiGet<ExternalStatement>(`/reconciliation/external/statements/${statementId}`);
    return { statement };
  } catch (error) {
    return handleAvailability(error, { statement: null, unavailable: true });
  }
};

export const createFixtureBundle = async (payload: {
  scenario: ReconciliationFixtureScenario;
  invoice_id: string;
  org_id: number;
  format: ReconciliationFixtureFormat;
  currency: string;
  wrong_amount_mode?: ReconciliationFixtureWrongAmountMode;
  amount_delta?: number;
  payer_inn?: string;
  payer_name?: string;
  seed?: string;
}): Promise<ReconciliationFixtureBundle> => {
  try {
    return await apiPost<ReconciliationFixtureBundle>("/reconciliation/fixtures", payload);
  } catch (error) {
    return handleAvailability(error, {
      bundle_id: "",
      files: [],
      notes: "",
      unavailable: true,
    });
  }
};

export const createFixtureImport = async (
  bundleId: string,
  payload: { format: "CSV" | "CLIENT_BANK_1C" | "MT940"; file_name: string },
): Promise<ReconciliationFixtureImportResult> => {
  try {
    return await apiPost<ReconciliationFixtureImportResult>(
      `/reconciliation/fixtures/${bundleId}/create-import`,
      payload,
    );
  } catch (error) {
    return handleAvailability(error, {
      import_id: "",
      object_key: "",
      unavailable: true,
    });
  }
};

export const completeStatementImport = async (
  importId: string,
  payload: { object_key: string },
): Promise<ReconciliationImportCompleteResult> => {
  try {
    return await apiPost<ReconciliationImportCompleteResult>(
      `/reconciliation/imports/${importId}/complete`,
      payload,
    );
  } catch (error) {
    return handleAvailability(error, {
      id: "",
      status: "",
      unavailable: true,
    });
  }
};
