import { request } from "./http";
import type { PaginatedResponse } from "./partner";
import type { Offer, OfferInput } from "../types/marketplace";

export interface OfferFilters {
  catalog_item_id?: string;
  active?: string;
  location_id?: string;
}

const toQuery = (filters: OfferFilters): string => {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value) {
      params.set(key, value);
    }
  });
  const query = params.toString();
  return query ? `?${query}` : "";
};

export const fetchOffers = (token: string, filters: OfferFilters = {}) =>
  request<PaginatedResponse<Offer>>(`/partner/offers${toQuery(filters)}`, {}, token);

export const createOffer = (token: string, payload: OfferInput) =>
  request<Offer>("/partner/offers", { method: "POST", body: JSON.stringify(payload) }, token);

export const updateOffer = (token: string, id: string, payload: OfferInput) =>
  request<Offer>(`/partner/offers/${id}`, { method: "PUT", body: JSON.stringify(payload) }, token);

export const activateOffer = (token: string, id: string) =>
  request(`/partner/offers/${id}/activate`, { method: "POST" }, token);

export const disableOffer = (token: string, id: string) =>
  request(`/partner/offers/${id}/disable`, { method: "POST" }, token);
