import { request, requestWithMeta } from "./http";
import type {
  MarketplaceOffer,
  MarketplaceOfferInput,
  MarketplaceOfferListResponse,
  MarketplaceOfferSummary,
  MarketplaceOfferUpdate,
} from "../types/marketplace";

export interface MarketplaceOfferFilters {
  status?: string;
  subject_type?: string;
  subject_id?: string;
  q?: string;
}

const toQuery = (filters: MarketplaceOfferFilters): string => {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value) {
      params.set(key, value);
    }
  });
  const query = params.toString();
  return query ? `?${query}` : "";
};

export const fetchMarketplaceOffers = (token: string, filters: MarketplaceOfferFilters = {}) =>
  request<MarketplaceOfferListResponse>(`/marketplace/partner/offers${toQuery(filters)}`, {}, token);

export const fetchMarketplaceOffer = (token: string, offerId: string) =>
  request<MarketplaceOffer>(`/marketplace/partner/offers/${offerId}`, {}, token);

export const createMarketplaceOffer = (token: string, payload: MarketplaceOfferInput) =>
  requestWithMeta<MarketplaceOffer>(
    "/marketplace/partner/offers",
    { method: "POST", body: JSON.stringify(payload) },
    token,
  );

export const updateMarketplaceOffer = (token: string, offerId: string, payload: MarketplaceOfferUpdate) =>
  requestWithMeta<MarketplaceOffer>(
    `/marketplace/partner/offers/${offerId}`,
    { method: "PATCH", body: JSON.stringify(payload) },
    token,
  );

export const submitMarketplaceOffer = (token: string, offerId: string) =>
  requestWithMeta<MarketplaceOffer>(`/marketplace/partner/offers/${offerId}:submit`, { method: "POST" }, token);

export const archiveMarketplaceOffer = (token: string, offerId: string) =>
  requestWithMeta<MarketplaceOffer>(`/marketplace/partner/offers/${offerId}:archive`, { method: "POST" }, token);

export type { MarketplaceOfferSummary };
