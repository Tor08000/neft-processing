import { request } from "./http";
import type {
  PartnerBalance,
  PartnerDocumentListResponse,
  PartnerLedgerListResponse,
  PartnerPayoutListResponse,
} from "../types/partnerFinance";

export const fetchPartnerBalance = (token: string) => request<PartnerBalance>("/partner/balance", {}, token, "core_root");

export const fetchPartnerLedger = (token: string) =>
  request<PartnerLedgerListResponse>("/partner/ledger", {}, token, "core_root");

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

export const fetchPartnerPayouts = (token: string) =>
  request<PartnerPayoutListResponse>("/partner/payouts", {}, token, "core_root");

export const fetchPartnerInvoices = (token: string) =>
  request<PartnerDocumentListResponse>("/partner/invoices", {}, token, "core_root");

export const fetchPartnerActs = (token: string) =>
  request<PartnerDocumentListResponse>("/partner/acts", {}, token, "core_root");
