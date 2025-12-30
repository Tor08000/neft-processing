import { request, requestWithMeta } from "./http";
import type { AuthSession } from "./types";
import type {
  MarketplaceCatalogResponse,
  MarketplaceCreateOrderPayload,
  MarketplaceCreateOrderResponse,
  MarketplaceOrderDetails,
  MarketplaceOrderDocumentsResponse,
  MarketplaceOrderEvent,
  MarketplaceOrdersResponse,
  MarketplaceServiceDetails,
} from "../types/marketplace";

const withToken = (user: AuthSession | null): string | undefined => user?.token;

interface MarketplaceCatalogFilters {
  category?: string;
  partner?: string;
  location?: string;
  availability?: string;
  priceFrom?: string;
  priceTo?: string;
}

interface MarketplaceOrdersFilters {
  from?: string;
  to?: string;
  status?: string;
  partner?: string;
  service?: string;
  limit?: number;
  offset?: number;
}

export function fetchMarketplaceCatalog(
  user: AuthSession | null,
  filters: MarketplaceCatalogFilters = {},
): Promise<MarketplaceCatalogResponse> {
  const search = new URLSearchParams();
  if (filters.category) search.set("category", filters.category);
  if (filters.partner) search.set("partner", filters.partner);
  if (filters.location) search.set("location", filters.location);
  if (filters.availability) search.set("availability", filters.availability);
  if (filters.priceFrom) search.set("price_from", filters.priceFrom);
  if (filters.priceTo) search.set("price_to", filters.priceTo);
  const query = search.toString();
  const path = query ? `/marketplace/catalog?${query}` : "/marketplace/catalog";
  return request<MarketplaceCatalogResponse>(path, { method: "GET" }, withToken(user));
}

export function fetchMarketplaceService(
  user: AuthSession | null,
  serviceId: string,
): Promise<MarketplaceServiceDetails> {
  return request<MarketplaceServiceDetails>(`/marketplace/services/${serviceId}`, { method: "GET" }, withToken(user));
}

export function createMarketplaceOrder(
  user: AuthSession | null,
  payload: MarketplaceCreateOrderPayload,
) {
  return requestWithMeta<MarketplaceCreateOrderResponse>(
    "/marketplace/orders",
    { method: "POST", body: JSON.stringify(payload) },
    withToken(user),
  );
}

export function fetchMarketplaceOrders(
  user: AuthSession | null,
  filters: MarketplaceOrdersFilters = {},
): Promise<MarketplaceOrdersResponse> {
  const search = new URLSearchParams();
  if (filters.from) search.set("from", filters.from);
  if (filters.to) search.set("to", filters.to);
  if (filters.status) search.set("status", filters.status);
  if (filters.partner) search.set("partner", filters.partner);
  if (filters.service) search.set("service", filters.service);
  if (filters.limit) search.set("limit", filters.limit.toString());
  if (filters.offset) search.set("offset", filters.offset.toString());
  const query = search.toString();
  const path = query ? `/marketplace/orders?${query}` : "/marketplace/orders";
  return request<MarketplaceOrdersResponse>(path, { method: "GET" }, withToken(user));
}

export function fetchMarketplaceOrderDetails(
  user: AuthSession | null,
  orderId: string,
): Promise<MarketplaceOrderDetails> {
  return request<MarketplaceOrderDetails>(`/marketplace/orders/${orderId}`, { method: "GET" }, withToken(user));
}

export function fetchMarketplaceOrderEvents(
  user: AuthSession | null,
  orderId: string,
): Promise<MarketplaceOrderEvent[]> {
  return request<MarketplaceOrderEvent[]>(`/marketplace/orders/${orderId}/events`, { method: "GET" }, withToken(user));
}

export function fetchMarketplaceOrderDocuments(
  user: AuthSession | null,
  orderId: string,
): Promise<MarketplaceOrderDocumentsResponse> {
  return request<MarketplaceOrderDocumentsResponse>(
    `/marketplace/orders/${orderId}/documents`,
    { method: "GET" },
    withToken(user),
  );
}
