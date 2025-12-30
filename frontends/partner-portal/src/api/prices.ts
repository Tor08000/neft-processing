import { request, requestWithMeta } from "./http";
import type {
  DiffResult,
  PriceAuditResponse,
  PriceImportResult,
  PriceAnalyticsInsight,
  PriceAnalyticsOffer,
  PriceAnalyticsSeriesPoint,
  PriceAnalyticsVersion,
  PriceItemsResponse,
  PriceVersion,
  PriceVersionsResponse,
  ValidationResult,
} from "../types/prices";

export interface PriceVersionsFilters {
  station_id?: string;
  status?: string;
  from?: string;
  to?: string;
}

export interface CreatePriceVersionRequest {
  station_scope: "all" | "list";
  station_ids?: string[];
  meta?: Record<string, string | number | boolean | null>;
}

export interface ImportPriceVersionRequest {
  format: "CSV" | "JSON";
  content_base64: string;
}

export interface PriceAnalyticsFilters {
  from: string;
  to: string;
}

export interface PriceAnalyticsOffersFilters extends PriceAnalyticsFilters {
  price_version_id?: string;
}

export interface PriceAnalyticsSeriesFilters extends PriceAnalyticsFilters {
  price_version_id: string;
}

const toQuery = (filters: PriceVersionsFilters): string => {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value) {
      params.set(key, value);
    }
  });
  const query = params.toString();
  return query ? `?${query}` : "";
};

export const fetchPriceVersions = (token: string, filters: PriceVersionsFilters) =>
  request<PriceVersionsResponse>(`/partner/prices/versions${toQuery(filters)}`, {}, token);

export const createPriceVersion = (token: string, payload: CreatePriceVersionRequest) =>
  requestWithMeta<PriceVersion>(`/partner/prices/versions`, { method: "POST", body: JSON.stringify(payload) }, token);

export const fetchPriceVersion = (token: string, versionId: string) =>
  request<PriceVersion>(`/partner/prices/versions/${versionId}`, {}, token);

export const validatePriceVersion = (token: string, versionId: string) =>
  requestWithMeta<ValidationResult>(`/partner/prices/versions/${versionId}/validate`, { method: "POST" }, token);

export const publishPriceVersion = (token: string, versionId: string) =>
  requestWithMeta<PriceVersion>(`/partner/prices/versions/${versionId}/publish`, { method: "POST" }, token);

export const rollbackPriceVersion = (token: string, versionId: string) =>
  requestWithMeta<PriceVersion>(`/partner/prices/versions/${versionId}/rollback`, { method: "POST" }, token);

export const importPriceVersion = (token: string, versionId: string, payload: ImportPriceVersionRequest) =>
  requestWithMeta<PriceImportResult>(
    `/partner/prices/versions/${versionId}/import`,
    { method: "POST", body: JSON.stringify(payload) },
    token,
  );

export const fetchPriceVersionItems = (token: string, versionId: string, params: Record<string, string | number>) => {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      query.set(key, String(value));
    }
  });
  const search = query.toString();
  return request<PriceItemsResponse>(`/partner/prices/versions/${versionId}/items${search ? `?${search}` : ""}`, {}, token);
};

export const fetchPriceVersionDiff = (token: string, versionId: string, toVersionId: string) =>
  request<DiffResult>(`/partner/prices/versions/${versionId}/diff?to_version_id=${toVersionId}`, {}, token);

export const fetchPriceVersionAudit = (token: string, versionId: string) =>
  request<PriceAuditResponse>(`/partner/prices/versions/${versionId}/audit`, {}, token);

const toAnalyticsQuery = (filters: Record<string, string | undefined>): string => {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value) {
      params.set(key, value);
    }
  });
  const query = params.toString();
  return query ? `?${query}` : "";
};

export const fetchPriceAnalyticsVersions = (token: string, filters: PriceAnalyticsFilters) =>
  request<PriceAnalyticsVersion[]>(`/partner/prices/analytics/versions${toAnalyticsQuery(filters)}`, {}, token);

export const fetchPriceAnalyticsVersionSeries = (token: string, filters: PriceAnalyticsSeriesFilters) =>
  request<PriceAnalyticsSeriesPoint[]>(`/partner/prices/analytics/versions/series${toAnalyticsQuery(filters)}`, {}, token);

export const fetchPriceAnalyticsOffers = (token: string, filters: PriceAnalyticsOffersFilters) =>
  request<PriceAnalyticsOffer[]>(`/partner/prices/analytics/offers${toAnalyticsQuery(filters)}`, {}, token);

export const fetchPriceAnalyticsInsights = (token: string, filters: PriceAnalyticsFilters) =>
  request<PriceAnalyticsInsight[]>(`/partner/prices/analytics/insights${toAnalyticsQuery(filters)}`, {}, token);
