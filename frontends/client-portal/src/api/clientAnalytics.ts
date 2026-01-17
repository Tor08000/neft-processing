import { request } from "./http";
import type { AuthSession } from "./types";
import type {
  ClientAnalyticsDrillResponse,
  ClientAnalyticsSupportDrillResponse,
  ClientAnalyticsSummaryResponse,
} from "../types/clientAnalytics";

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

export interface ClientAnalyticsDrillDayQuery {
  date: string;
  timezone?: string;
  limit?: number;
  cursor?: string | null;
}

export function fetchClientAnalyticsDayDrill(
  user: AuthSession | null,
  params: ClientAnalyticsDrillDayQuery,
): Promise<ClientAnalyticsDrillResponse> {
  const search = new URLSearchParams({ date: params.date });
  if (params.timezone) {
    search.set("timezone", params.timezone);
  }
  if (params.limit) {
    search.set("limit", String(params.limit));
  }
  if (params.cursor) {
    search.set("cursor", params.cursor);
  }
  return request<ClientAnalyticsDrillResponse>(`/client/analytics/drill/day?${search.toString()}`, { method: "GET" }, withToken(user));
}

export interface ClientAnalyticsDrillRangeQuery {
  from: string;
  to: string;
  limit?: number;
  cursor?: string | null;
}

export function fetchClientAnalyticsCardDrill(
  user: AuthSession | null,
  cardId: string,
  params: ClientAnalyticsDrillRangeQuery,
): Promise<ClientAnalyticsDrillResponse> {
  const search = new URLSearchParams({ from: params.from, to: params.to });
  if (params.limit) {
    search.set("limit", String(params.limit));
  }
  if (params.cursor) {
    search.set("cursor", params.cursor);
  }
  return request<ClientAnalyticsDrillResponse>(
    `/client/analytics/drill/card/${cardId}?${search.toString()}`,
    { method: "GET" },
    withToken(user),
  );
}

export function fetchClientAnalyticsDriverDrill(
  user: AuthSession | null,
  userId: string,
  params: ClientAnalyticsDrillRangeQuery,
): Promise<ClientAnalyticsDrillResponse> {
  const search = new URLSearchParams({ from: params.from, to: params.to });
  if (params.limit) {
    search.set("limit", String(params.limit));
  }
  if (params.cursor) {
    search.set("cursor", params.cursor);
  }
  return request<ClientAnalyticsDrillResponse>(
    `/client/analytics/drill/driver/${userId}?${search.toString()}`,
    { method: "GET" },
    withToken(user),
  );
}

export interface ClientAnalyticsSupportDrillQuery extends ClientAnalyticsDrillRangeQuery {
  filter?: string;
}

export function fetchClientAnalyticsSupportDrill(
  user: AuthSession | null,
  params: ClientAnalyticsSupportDrillQuery,
): Promise<ClientAnalyticsSupportDrillResponse> {
  const search = new URLSearchParams({ from: params.from, to: params.to });
  if (params.filter) {
    search.set("t", params.filter);
  }
  if (params.limit) {
    search.set("limit", String(params.limit));
  }
  if (params.cursor) {
    search.set("cursor", params.cursor);
  }
  return request<ClientAnalyticsSupportDrillResponse>(
    `/client/analytics/drill/support?${search.toString()}`,
    { method: "GET" },
    withToken(user),
  );
}
