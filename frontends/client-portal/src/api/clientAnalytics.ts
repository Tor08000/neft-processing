import { request } from "./http";
import type { AuthSession } from "./types";
import type { ClientAnalyticsSummaryResponse } from "../types/clientAnalytics";

const withToken = (user: AuthSession | null): string | undefined => user?.token;

export interface ClientAnalyticsQuery {
  from: string;
  to: string;
  scope?: string;
  timezone?: string;
}

export function fetchClientAnalyticsSummary(
  user: AuthSession | null,
  params: ClientAnalyticsQuery,
): Promise<ClientAnalyticsSummaryResponse> {
  const search = new URLSearchParams({
    from: params.from,
    to: params.to,
  });
  if (params.scope) {
    search.set("scope", params.scope);
  }
  if (params.timezone) {
    search.set("timezone", params.timezone);
  }
  return request<ClientAnalyticsSummaryResponse>(`/client/analytics/summary?${search.toString()}`, { method: "GET" }, withToken(user));
}
