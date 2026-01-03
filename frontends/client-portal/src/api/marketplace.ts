import { request, requestWithMeta } from "./http";
import type { AuthSession } from "./types";
import type {
  MarketplaceCreateOrderPayload,
  MarketplaceCreateOrderResponse,
  MarketplaceOrderDetails,
  MarketplaceOrderDocumentsResponse,
  MarketplaceOrderEvent,
  MarketplaceOrderConsequencesResponse,
  MarketplaceOrderSlaResponse,
  MarketplaceOrdersResponse,
  MarketplaceProductDetails,
  MarketplaceProductListResponse,
  MarketplaceProductOrderPayload,
  MarketplaceOrderInvoice,
} from "../types/marketplace";
import type { CaseListResponse } from "../types/cases";

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
  category?: string;
  q?: string;
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
  if (filters.category) search.set("category", filters.category);
  if (filters.q) search.set("q", filters.q);
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

export function cancelMarketplaceOrder(user: AuthSession | null, orderId: string) {
  return requestWithMeta<Record<string, never>>(
    `/marketplace/orders/${orderId}/cancel`,
    { method: "POST" },
    withToken(user),
  );
}

export function fetchMarketplaceOrderSla(
  user: AuthSession | null,
  orderId: string,
): Promise<MarketplaceOrderSlaResponse> {
  return request<MarketplaceOrderSlaResponse>(`/marketplace/orders/${orderId}/sla`, { method: "GET" }, withToken(user));
}

export function fetchMarketplaceOrderConsequences(
  user: AuthSession | null,
  orderId: string,
): Promise<MarketplaceOrderConsequencesResponse> {
  return request<MarketplaceOrderConsequencesResponse>(
    `/marketplace/orders/${orderId}/consequences`,
    { method: "GET" },
    withToken(user),
  );
}

export function fetchMarketplaceOrderInvoices(
  user: AuthSession | null,
  orderId: string,
): Promise<MarketplaceOrderInvoice[]> {
  return request<MarketplaceOrderInvoice[]>(
    `/client/billing/invoices?order_id=${encodeURIComponent(orderId)}`,
    { method: "GET" },
    { token: user?.token ?? null, base: "core_root" },
  );
}

export function fetchMarketplaceOrderIncidents(
  user: AuthSession | null,
  orderId: string,
): Promise<CaseListResponse> {
  return request<CaseListResponse>(
    `/client/cases?order_id=${encodeURIComponent(orderId)}`,
    { method: "GET" },
    { token: user?.token ?? null, base: "core_root" },
  );
}
