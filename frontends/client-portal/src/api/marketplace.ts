import { request, requestWithMeta } from "./http";
import type { AuthSession } from "./types";
import type {
  MarketplaceCreateOrderPayload,
  MarketplaceCreateOrderResponse,
  MarketplaceClientEventInput,
  MarketplaceClientEventsIngestResponse,
  MarketplaceOrderDetails,
  MarketplaceOrderEvent,
  MarketplaceOrderConsequencesResponse,
  MarketplaceOrderSlaResponse,
  MarketplaceOrdersResponse,
  MarketplaceProductDetails,
  MarketplaceProductListResponse,
  MarketplaceProductOffersResponse,
  MarketplaceRecommendationWhyResponse,
  MarketplaceRecommendationsResponse,
} from "../types/marketplace";
import type { CaseListResponse } from "../types/cases";

const withToken = (user: AuthSession | null): string | undefined => user?.token;

interface MarketplaceProductFilters {
  q?: string;
  category?: string;
  type?: string;
  limit?: number;
  offset?: number;
}

interface MarketplaceOrdersFilters {
  status?: string;
  limit?: number;
  offset?: number;
}

export function listMarketplaceProducts(
  user: AuthSession | null,
  filters: MarketplaceProductFilters = {},
): Promise<MarketplaceProductListResponse> {
  const search = new URLSearchParams();
  if (filters.q) search.set("q", filters.q);
  if (filters.category) search.set("category", filters.category);
  if (filters.type) search.set("type", filters.type);
  if (filters.limit) search.set("limit", filters.limit.toString());
  if (filters.offset) search.set("offset", filters.offset.toString());
  const query = search.toString();
  const path = query ? `/client/marketplace/products?${query}` : "/client/marketplace/products";
  return request<MarketplaceProductListResponse>(path, { method: "GET" }, withToken(user));
}

export function getMarketplaceProduct(
  user: AuthSession | null,
  productId: string,
): Promise<MarketplaceProductDetails> {
  return request<MarketplaceProductDetails>(`/client/marketplace/products/${productId}`, { method: "GET" }, withToken(user));
}

export function fetchMarketplaceProductOffers(
  user: AuthSession | null,
  productId: string,
): Promise<MarketplaceProductOffersResponse> {
  return request<MarketplaceProductOffersResponse>(
    `/client/marketplace/products/${productId}/offers`,
    { method: "GET" },
    withToken(user),
  );
}

export function createMarketplaceOrder(
  user: AuthSession | null,
  payload: MarketplaceCreateOrderPayload,
) {
  return requestWithMeta<MarketplaceCreateOrderResponse>(
    "/v1/marketplace/client/orders",
    { method: "POST", body: JSON.stringify(payload) },
    withToken(user),
  );
}

export function fetchMarketplaceOrders(
  user: AuthSession | null,
  filters: MarketplaceOrdersFilters = {},
): Promise<MarketplaceOrdersResponse> {
  const search = new URLSearchParams();
  if (filters.status) search.set("status", filters.status);
  if (filters.limit) search.set("limit", filters.limit.toString());
  if (filters.offset) search.set("offset", filters.offset.toString());
  const query = search.toString();
  const path = query ? `/v1/marketplace/client/orders?${query}` : "/v1/marketplace/client/orders";
  return request<MarketplaceOrdersResponse>(path, { method: "GET" }, withToken(user));
}

export function fetchMarketplaceOrderDetails(
  user: AuthSession | null,
  orderId: string,
): Promise<MarketplaceOrderDetails> {
  return request<MarketplaceOrderDetails>(`/v1/marketplace/client/orders/${orderId}`, { method: "GET" }, withToken(user));
}

export function fetchMarketplaceOrderEvents(
  user: AuthSession | null,
  orderId: string,
): Promise<MarketplaceOrderEvent[]> {
  return request<MarketplaceOrderEvent[]>(
    `/v1/marketplace/client/orders/${orderId}/events`,
    { method: "GET" },
    withToken(user),
  );
}


export function cancelMarketplaceOrder(user: AuthSession | null, orderId: string, reason: string | null = null) {
  return requestWithMeta<Record<string, never>>(
    `/v1/marketplace/client/orders/${orderId}/cancel`,
    { method: "POST", body: JSON.stringify({ reason }) },
    withToken(user),
  );
}

export function payMarketplaceOrder(user: AuthSession | null, orderId: string, paymentMethod: string) {
  return requestWithMeta<Record<string, unknown>>(
    `/v1/marketplace/client/orders/${orderId}:pay`,
    { method: "POST", body: JSON.stringify({ payment_method: paymentMethod }) },
    withToken(user),
  );
}

export function fetchMarketplaceOrderSla(
  user: AuthSession | null,
  orderId: string,
): Promise<MarketplaceOrderSlaResponse> {
  return request<MarketplaceOrderSlaResponse>(
    `/client/marketplace/orders/${orderId}/sla`,
    { method: "GET" },
    withToken(user),
  );
}

export function fetchMarketplaceOrderConsequences(
  user: AuthSession | null,
  orderId: string,
): Promise<MarketplaceOrderConsequencesResponse> {
  return request<MarketplaceOrderConsequencesResponse>(
    `/client/marketplace/orders/${orderId}/consequences`,
    { method: "GET" },
    withToken(user),
  );
}


export function fetchMarketplaceOrderIncidents(
  user: AuthSession | null,
  orderId: string,
): Promise<CaseListResponse> {
  return request<CaseListResponse>(
    `/v1/marketplace/client/orders/${orderId}/incidents`,
    { method: "GET" },
    withToken(user),
  );
}

export function sendMarketplaceClientEvents(
  user: AuthSession | null,
  events: MarketplaceClientEventInput[],
): Promise<MarketplaceClientEventsIngestResponse> {
  return request<MarketplaceClientEventsIngestResponse>(
    "/v1/marketplace/client/events",
    { method: "POST", body: JSON.stringify({ events }) },
    withToken(user),
  );
}

export function listMarketplaceRecommendations(
  user: AuthSession | null,
  limit: number = 12,
  mode: string = "default",
): Promise<MarketplaceRecommendationsResponse> {
  const search = new URLSearchParams({ limit: limit.toString(), mode });
  return request<MarketplaceRecommendationsResponse>(
    `/v1/marketplace/client/recommendations?${search.toString()}`,
    { method: "GET" },
    withToken(user),
  );
}

export function fetchMarketplaceRecommendationWhy(
  user: AuthSession | null,
  offerId: string,
): Promise<MarketplaceRecommendationWhyResponse> {
  const search = new URLSearchParams({ offer_id: offerId });
  return request<MarketplaceRecommendationWhyResponse>(
    `/v1/marketplace/client/recommendations/why?${search.toString()}`,
    { method: "GET" },
    withToken(user),
  );
}
