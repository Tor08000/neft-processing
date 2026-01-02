import { request } from "./http";
import type { AuthSession } from "./types";
import type {
  PartnerContractsResponse,
  PartnerDashboardSummary,
  PartnerSettlementDetails,
  PartnerSettlementListResponse,
} from "../types/portal";

const withToken = (user: AuthSession | null) => ({ token: user?.token, base: "core_root" as const });

export const fetchPartnerDashboard = (user: AuthSession | null) =>
  request<PartnerDashboardSummary>("/partner/dashboard", { method: "GET" }, withToken(user));

export const fetchPartnerContracts = (user: AuthSession | null) =>
  request<PartnerContractsResponse>("/partner/contracts", { method: "GET" }, withToken(user));

export const fetchPartnerSettlements = (user: AuthSession | null) =>
  request<PartnerSettlementListResponse>("/partner/settlements", { method: "GET" }, withToken(user));

export const fetchPartnerSettlementDetails = (user: AuthSession | null, settlementRef: string) =>
  request<PartnerSettlementDetails>(`/partner/settlements/${settlementRef}`, { method: "GET" }, withToken(user));

export const confirmPartnerSettlement = (user: AuthSession | null, settlementRef: string) =>
  request(`/partner/settlements/${settlementRef}/confirm`, { method: "POST" }, withToken(user));
