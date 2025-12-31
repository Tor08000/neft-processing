import { request } from "./http";
import type { AuthSession } from "./types";
import type {
  AnalyticsDailyMetricsResponse,
  AnalyticsDeclinesResponse,
  AnalyticsDocumentsSummaryResponse,
  AnalyticsExportRequest,
  AnalyticsExportResponse,
  AnalyticsExportsSummaryResponse,
  AnalyticsOrdersSummaryResponse,
  AnalyticsSpendSummaryResponse,
} from "../types/analytics";

const withToken = (user: AuthSession | null): string | undefined => user?.token;

export interface AnalyticsScopeParams {
  scopeType: "CLIENT";
  scopeId: string;
  from: string;
  to: string;
}

export function fetchDailyMetrics(
  user: AuthSession | null,
  params: AnalyticsScopeParams,
): Promise<AnalyticsDailyMetricsResponse> {
  const search = new URLSearchParams({
    scope_type: params.scopeType,
    scope_id: params.scopeId,
    from: params.from,
    to: params.to,
  });
  return request<AnalyticsDailyMetricsResponse>(`/bi/metrics/daily?${search.toString()}`, { method: "GET" }, withToken(user));
}

export interface DeclinesParams {
  clientId: string;
  from: string;
  to: string;
  reason?: string;
  stationId?: string;
}

export function fetchDeclines(user: AuthSession | null, params: DeclinesParams): Promise<AnalyticsDeclinesResponse> {
  const search = new URLSearchParams({
    client_id: params.clientId,
    from: params.from,
    to: params.to,
  });
  if (params.reason) search.set("reason", params.reason);
  if (params.stationId) search.set("station_id", params.stationId);
  return request<AnalyticsDeclinesResponse>(`/bi/declines?${search.toString()}`, { method: "GET" }, withToken(user));
}

export interface OrdersParams {
  clientId: string;
  from: string;
  to: string;
  status?: string;
}

export function fetchOrdersSummary(
  user: AuthSession | null,
  params: OrdersParams,
): Promise<AnalyticsOrdersSummaryResponse> {
  const search = new URLSearchParams({
    client_id: params.clientId,
    from: params.from,
    to: params.to,
  });
  if (params.status) search.set("status", params.status);
  return request<AnalyticsOrdersSummaryResponse>(`/bi/orders/summary?${search.toString()}`, { method: "GET" }, withToken(user));
}

export interface DocumentsParams {
  clientId: string;
  from: string;
  to: string;
}

export function fetchDocumentsSummary(
  user: AuthSession | null,
  params: DocumentsParams,
): Promise<AnalyticsDocumentsSummaryResponse> {
  const search = new URLSearchParams({
    client_id: params.clientId,
    from: params.from,
    to: params.to,
  });
  return request<AnalyticsDocumentsSummaryResponse>(`/bi/documents/summary?${search.toString()}`, { method: "GET" }, withToken(user));
}

export interface ExportsParams {
  clientId: string;
  from: string;
  to: string;
}

export function fetchExportsSummary(
  user: AuthSession | null,
  params: ExportsParams,
): Promise<AnalyticsExportsSummaryResponse> {
  const search = new URLSearchParams({
    client_id: params.clientId,
    from: params.from,
    to: params.to,
  });
  return request<AnalyticsExportsSummaryResponse>(`/bi/exports/summary?${search.toString()}`, { method: "GET" }, withToken(user));
}

export interface SpendParams {
  clientId: string;
  from: string;
  to: string;
}

export function fetchSpendSummary(
  user: AuthSession | null,
  params: SpendParams,
): Promise<AnalyticsSpendSummaryResponse> {
  const search = new URLSearchParams({
    client_id: params.clientId,
    from: params.from,
    to: params.to,
  });
  return request<AnalyticsSpendSummaryResponse>(`/bi/spend/summary?${search.toString()}`, { method: "GET" }, withToken(user));
}

export function createAnalyticsExport(
  user: AuthSession | null,
  payload: AnalyticsExportRequest,
): Promise<AnalyticsExportResponse> {
  return request<AnalyticsExportResponse>(
    "/bi/exports",
    { method: "POST", body: JSON.stringify(payload) },
    withToken(user),
  );
}
