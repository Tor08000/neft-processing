import { request, requestWithMeta } from "./http";
import type { AuthSession } from "./types";
import type {
  MarketplaceCreateOrderPayload,
  MarketplaceCreateOrderResponse,
  MarketplaceOrderDetails,
  MarketplaceOrderDocumentsResponse,
  MarketplaceOrderEvent,
  MarketplaceOrdersResponse,
  MarketplaceProductDetails,
  MarketplaceProductListResponse,
  MarketplaceProductOrderPayload,
} from "../types/marketplace";

const withToken = (user: AuthSession | null): string | undefined => user?.token;

interface MarketplaceProductFilters {
  q?: string;
  category?: string;
  type?: string;
  priceModel?: string;
  partnerId?: string;
  sort?: string;
  limit?: number;
  offset?: number;
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

export function listMarketplaceProducts(
  user: AuthSession | null,
  filters: MarketplaceProductFilters = {},
): Promise<MarketplaceProductListResponse> {
  const search = new URLSearchParams();
  if (filters.q) search.set("q", filters.q);
  if (filters.category) search.set("category", filters.category);
  if (filters.type) search.set("type", filters.type);
  if (filters.priceModel) search.set("price_model", filters.priceModel);
  if (filters.partnerId) search.set("partner_id", filters.partnerId);
  if (filters.sort) search.set("sort", filters.sort);
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

export function createMarketplaceProductOrder(
  user: AuthSession | null,
  payload: MarketplaceProductOrderPayload,
) {
  return requestWithMeta<Record<string, never>>(
    "/client/marketplace/orders",
    { method: "POST", body: JSON.stringify(payload) },
    withToken(user),
  );
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
