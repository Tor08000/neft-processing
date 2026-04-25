import { request } from "./http";
import type { AuthSession, PortalMeResponse } from "./types";
import type { PartnerDashboardSummary } from "../types/portal";

const withToken = (user: AuthSession | null) => ({ token: user?.token, base: "core_root" as const });

export const fetchPartnerDashboard = (user: AuthSession | null) =>
  request<PartnerDashboardSummary>("/partner/finance/dashboard", { method: "GET" }, withToken(user));

export const verifyPartnerAuth = (user: AuthSession | null) =>
  request("/partner/auth/verify", { method: "GET" }, withToken(user));

export const fetchPortalMe = (user: AuthSession | null) =>
  request<PortalMeResponse>("/portal/me", { method: "GET" }, withToken(user));
