import { request, requestWithMeta } from "./http";
import type { PaginatedResponse } from "./partner";
import type { MarketplaceOrder, MarketplaceOrderActionResult } from "../types/marketplace";

export interface OrderFilters {
  status?: string;
  from?: string;
  to?: string;
  q?: string;
  limit?: string;
  offset?: string;
}

const toQuery = (filters: OrderFilters): string => {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value) {
      params.set(key, value);
    }
  });
  const query = params.toString();
  return query ? `?${query}` : "";
};

export const fetchOrders = (token: string, filters: OrderFilters = {}) =>
  request<PaginatedResponse<MarketplaceOrder>>(`/partner/orders${toQuery(filters)}`, {}, token);

export const fetchOrder = (token: string, id: string) => request<MarketplaceOrder>(`/partner/orders/${id}`, {}, token);

export const confirmOrder = async (token: string, id: string) => {
  const { data, correlationId } = await requestWithMeta<MarketplaceOrderActionResult>(
    `/partner/orders/${id}/confirm`,
    { method: "POST" },
    token,
  );
  return { ...data, correlationId };
};

export const startOrder = async (token: string, id: string) => {
  const { data, correlationId } = await requestWithMeta<MarketplaceOrderActionResult>(
    `/partner/orders/${id}/start`,
    { method: "POST" },
    token,
  );
  return { ...data, correlationId };
};

export const completeOrder = async (token: string, id: string) => {
  const { data, correlationId } = await requestWithMeta<MarketplaceOrderActionResult>(
    `/partner/orders/${id}/complete`,
    { method: "POST" },
    token,
  );
  return { ...data, correlationId };
};

export const cancelOrder = async (token: string, id: string, reason: string) => {
  const { data, correlationId } = await requestWithMeta<MarketplaceOrderActionResult>(
    `/partner/orders/${id}/cancel`,
    { method: "POST", body: JSON.stringify({ reason }) },
    token,
  );
  return { ...data, correlationId };
};
