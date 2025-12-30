import { request, requestFormData } from "./http";
import type { PaginatedResponse } from "./partner";
import type { CatalogImportPreview, CatalogImportSummary, CatalogItem, CatalogItemInput } from "../types/marketplace";

export interface CatalogFilters {
  kind?: string;
  status?: string;
  category?: string;
  q?: string;
  limit?: string;
  offset?: string;
}

const toQuery = (filters: CatalogFilters): string => {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value) {
      params.set(key, value);
    }
  });
  const query = params.toString();
  return query ? `?${query}` : "";
};

export const fetchCatalogItems = (token: string, filters: CatalogFilters = {}) =>
  request<PaginatedResponse<CatalogItem>>(`/partner/catalog${toQuery(filters)}`, {}, token);

export const fetchCatalogItem = (token: string, id: string) => request<CatalogItem>(`/partner/catalog/${id}`, {}, token);

export const createCatalogItem = (token: string, payload: CatalogItemInput) =>
  request<CatalogItem>("/partner/catalog", { method: "POST", body: JSON.stringify(payload) }, token);

export const updateCatalogItem = (token: string, id: string, payload: CatalogItemInput) =>
  request<CatalogItem>(`/partner/catalog/${id}`, { method: "PUT", body: JSON.stringify(payload) }, token);

export const activateCatalogItem = (token: string, id: string) =>
  request(`/partner/catalog/${id}/activate`, { method: "POST" }, token);

export const disableCatalogItem = (token: string, id: string) =>
  request(`/partner/catalog/${id}/disable`, { method: "POST" }, token);

export const previewCatalogImport = (token: string, file: File) => {
  const data = new FormData();
  data.append("file", file);
  return requestFormData<CatalogImportPreview>("/partner/catalog/import?mode=preview", data, token);
};

export const applyCatalogImport = (token: string, file: File) => {
  const data = new FormData();
  data.append("file", file);
  return requestFormData<CatalogImportSummary>("/partner/catalog/import?mode=apply", data, token);
};
