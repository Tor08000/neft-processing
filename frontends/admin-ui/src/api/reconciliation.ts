import { apiGet, apiPost } from "./client";
import type {
  ReconciliationImport,
  ReconciliationImportListResponse,
  ReconciliationTransactionListResponse,
} from "../types/reconciliationImports";

export type ReconciliationScope = "internal" | "external" | "unknown";
export type ReconciliationRunStatus = "completed" | "failed" | "started" | "running" | "unknown";
export type ReconciliationDiscrepancyStatus = "open" | "resolved" | "ignored" | "unknown";
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
}

export interface ReconciliationDiscrepancyListResponse {
  discrepancies: ReconciliationDiscrepancy[];
  unavailable?: boolean;
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
    const response = await apiGet<{ runs: ReconciliationRun[] }>("/v1/admin/reconciliation/runs", params);
    return { runs: response.runs ?? [] };
  } catch (error) {
    return handleAvailability(error, { runs: [], unavailable: true });
  }
};

export const listImports = async (): Promise<ReconciliationImportListResponse> =>
  apiGet("/api/core/v1/admin/reconciliation/imports");

export const getImport = async (importId: string): Promise<ReconciliationImport> =>
  apiGet(`/api/core/v1/admin/reconciliation/imports/${importId}`);

export const listImportTransactions = async (params: {
  import_id?: string;
  status?: string;
}): Promise<ReconciliationTransactionListResponse> =>
  apiGet("/api/core/v1/admin/reconciliation/transactions", params);

export const parseImport = async (importId: string, reason: string) =>
  apiPost(`/api/core/v1/admin/reconciliation/imports/${importId}/parse`, { reason });

export const matchImport = async (importId: string, reason: string) =>
  apiPost(`/api/core/v1/admin/reconciliation/imports/${importId}/match`, { reason });

export const applyImportTransaction = async (transactionId: string, payload: { invoice_id: string; reason: string }) =>
  apiPost(`/api/core/v1/admin/reconciliation/transactions/${transactionId}/apply`, payload);

export const ignoreImportTransaction = async (transactionId: string, reason: string) =>
  apiPost(`/api/core/v1/admin/reconciliation/transactions/${transactionId}/ignore`, { reason });

export const createInternalRun = async (payload: {
  period_start: string;
  period_end: string;
}): Promise<ReconciliationRunResult> => {
  try {
    const run = await apiPost<ReconciliationRun>("/v1/admin/reconciliation/internal", payload);
    return { run };
  } catch (error) {
    return handleAvailability(error, { run: null, unavailable: true });
  }
};

export const createExternalRun = async (payload: { statement_id: string }): Promise<ReconciliationRunResult> => {
  try {
    const run = await apiPost<ReconciliationRun>("/v1/admin/reconciliation/external/run", payload);
    return { run };
  } catch (error) {
    return handleAvailability(error, { run: null, unavailable: true });
  }
};

export const getRun = async (runId: string): Promise<ReconciliationRunResult> => {
  try {
    const run = await apiGet<ReconciliationRun>(`/v1/admin/reconciliation/runs/${runId}`);
    return { run };
  } catch (error) {
    return handleAvailability(error, { run: null, unavailable: true });
  }
};

export const listDiscrepancies = async (
  runId: string,
  params?: { status?: string },
): Promise<ReconciliationDiscrepancyListResponse> => {
  try {
    const response = await apiGet<{ discrepancies: ReconciliationDiscrepancy[] }>(
      `/v1/admin/reconciliation/runs/${runId}/discrepancies`,
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
      `/v1/admin/reconciliation/discrepancies/${discrepancyId}/resolve-adjustment`,
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
      `/v1/admin/reconciliation/discrepancies/${discrepancyId}/ignore`,
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
    const response = await apiPost<ExternalStatement>("/v1/admin/reconciliation/external/statements", {
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
      "/v1/admin/reconciliation/external/statements",
      params,
    );
    return { statements: response.statements ?? [] };
  } catch (error) {
    return handleAvailability(error, { statements: [], unavailable: true });
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
    return await apiPost<ReconciliationFixtureBundle>("/v1/admin/reconciliation/fixtures", payload);
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
      `/v1/admin/reconciliation/fixtures/${bundleId}/create-import`,
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
      `/v1/admin/reconciliation/imports/${importId}/complete`,
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
