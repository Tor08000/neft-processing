import { request } from "./http";
import type {
  MarketplacePartnerProfile,
  MarketplaceProduct,
  MarketplaceProductInput,
  MarketplaceProductListResponse,
  MarketplaceProductMedia,
  MarketplaceProductUpdate,
} from "../types/marketplace";

const withToken = (token: string | null | undefined) => ({ token: token ?? undefined, base: "core_root" as const });

export interface MarketplaceProductFilters {
  status?: string;
  q?: string;
  category?: string;
  limit?: string;
  offset?: string;
}

const toQuery = (filters: MarketplaceProductFilters): string => {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value) {
      params.set(key, value);
    }
  });
  const query = params.toString();
  return query ? `?${query}` : "";
};

export const fetchMarketplaceProfile = (token: string | null | undefined) =>
  request<MarketplacePartnerProfile>("/partner/profile", {}, withToken(token));

export const upsertMarketplaceProfile = (token: string | null | undefined, payload: { company_name: string; description?: string | null }) =>
  request<MarketplacePartnerProfile>(
    "/partner/profile",
    { method: "POST", body: JSON.stringify(payload) },
    withToken(token),
  );

export const fetchMarketplaceProducts = (token: string | null | undefined, filters: MarketplaceProductFilters = {}) =>
  request<MarketplaceProductListResponse>(`/partner/products${toQuery(filters)}`, {}, withToken(token));

export const fetchMarketplaceProduct = (token: string | null | undefined, id: string) =>
  request<MarketplaceProduct>(`/partner/products/${id}`, {}, withToken(token));

export const createMarketplaceProduct = (token: string | null | undefined, payload: MarketplaceProductInput) =>
  request<MarketplaceProduct>("/partner/products", { method: "POST", body: JSON.stringify(payload) }, withToken(token));

export const updateMarketplaceProduct = (token: string | null | undefined, id: string, payload: MarketplaceProductUpdate) =>
  request<MarketplaceProduct>(
    `/partner/products/${id}`,
    { method: "PATCH", body: JSON.stringify(payload) },
    withToken(token),
  );

export const submitMarketplaceProduct = (token: string | null | undefined, id: string) =>
  request<MarketplaceProduct>(`/partner/products/${id}/submit`, { method: "POST" }, withToken(token));

export const archiveMarketplaceProduct = (token: string | null | undefined, id: string) =>
  request<MarketplaceProduct>(`/partner/products/${id}/archive`, { method: "POST" }, withToken(token));

export const addMarketplaceProductMedia = (
  token: string | null | undefined,
  productId: string,
  payload: MarketplaceProductMedia,
) =>
  request<MarketplaceProductMedia>(
    `/partner/products/${productId}/media`,
    { method: "POST", body: JSON.stringify(payload) },
    withToken(token),
  );

export const removeMarketplaceProductMedia = (token: string | null | undefined, productId: string, attachmentId: string) =>
  request<void>(`/partner/products/${productId}/media/${attachmentId}`, { method: "DELETE" }, withToken(token));
