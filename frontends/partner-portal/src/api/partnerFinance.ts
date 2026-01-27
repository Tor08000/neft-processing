import { request } from "./http";
import { CORE_ROOT_API_BASE } from "./base";
import type {
  PartnerBalance,
  PartnerDocumentListResponse,
  PartnerExportJobListResponse,
  PartnerLedgerExplain,
  PartnerLedgerListResponse,
  PartnerPayoutListResponse,
  PartnerPayoutPreview,
  PartnerPayoutTrace,
} from "../types/partnerFinance";

export const fetchPartnerBalance = (token: string) => request<PartnerBalance>("/partner/balance", {}, token, "core_root");

const buildQuery = (params: Record<string, string | number | undefined>) => {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") return;
    query.append(key, String(value));
  });
  const suffix = query.toString();
  return suffix ? `?${suffix}` : "";
};

export const fetchPartnerLedger = (token: string, params: { limit?: number; cursor?: string } = {}) => {
  const suffix = buildQuery(params);
  return request<PartnerLedgerListResponse>(`/partner/ledger${suffix}`, {}, token, "core_root");
};

export const fetchPartnerLedgerExplain = (token: string, entryId: string) =>
  request<PartnerLedgerExplain>(`/partner/ledger/${entryId}/explain`, {}, token, "core_root");

export const requestPartnerPayout = (token: string, amount: number, currency: string) =>
  request(
    "/partner/payouts/request",
    {
      method: "POST",
      body: JSON.stringify({ amount, currency }),
    },
    token,
    "core_root",
  );

export const fetchPartnerPayouts = (token: string, params: { limit?: number; cursor?: string } = {}) => {
  const suffix = buildQuery(params);
  return request<PartnerPayoutListResponse>(`/partner/payouts${suffix}`, {}, token, "core_root");
};

export const fetchPartnerPayoutPreview = (token: string) =>
  request<PartnerPayoutPreview>("/partner/payouts/preview", {}, token, "core_root");

export const fetchPartnerPayoutTrace = (token: string, payoutId: string) =>
  request<PartnerPayoutTrace>(`/partner/payouts/${payoutId}/trace`, {}, token, "core_root");

export const fetchPartnerInvoices = (token: string) =>
  request<PartnerDocumentListResponse>("/partner/invoices", {}, token, "core_root");

export const fetchPartnerActs = (token: string) =>
  request<PartnerDocumentListResponse>("/partner/acts", {}, token, "core_root");

export const createSettlementChainExport = (
  token: string,
  payload: { from: string; to: string; format: "CSV" | "ZIP" },
) =>
  request<{ id: string; status: string }>(
    "/partner/exports/settlement-chain",
    { method: "POST", body: JSON.stringify(payload) },
    token,
    "core_root",
  );

export const fetchPartnerExportJobs = (token: string, limit = 20) =>
  request<PartnerExportJobListResponse>(`/partner/exports/jobs?limit=${limit}`, {}, token, "core_root");

export const getPartnerExportDownloadUrl = (jobId: string) =>
  `${CORE_ROOT_API_BASE}/partner/exports/jobs/${jobId}/download`;
