import { request, requestWithMeta } from "./http";
import type { PaginatedResponse } from "./partner";
import type {
  MarketplaceDocumentDetails,
  MarketplaceEdoEvent,
  MarketplaceOrder,
  MarketplaceOrderActionResult,
  MarketplaceOrderEvent,
  MarketplaceOrderSlaResponse,
  MarketplaceSettlementLink,
} from "../types/marketplace";

export interface OrderFilters {
  status?: string;
  from?: string;
  to?: string;
  q?: string;
  limit?: string;
  offset?: string;
  station_id?: string;
  service_id?: string;
  sla_risk?: string;
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

export const fetchOrderEvents = (token: string, id: string) =>
  request<MarketplaceOrderEvent[]>(`/partner/orders/${id}/events`, {}, token);

export const fetchOrderDocuments = (token: string, id: string) =>
  request<MarketplaceDocumentDetails[]>(`/partner/orders/${id}/documents`, {}, token);

export const fetchDocumentDetails = (token: string, id: string) =>
  request<MarketplaceDocumentDetails>(`/partner/documents/${id}`, {}, token);

export const requestDocumentSignature = async (token: string, id: string) => {
  const { data, correlationId } = await requestWithMeta<MarketplaceOrderActionResult>(
    `/partner/documents/${id}/sign/request`,
    { method: "POST" },
    token,
  );
  return { ...data, correlationId };
};

export const dispatchDocumentEdo = async (token: string, id: string) => {
  const { data, correlationId } = await requestWithMeta<MarketplaceOrderActionResult>(
    `/partner/documents/${id}/edo/dispatch`,
    { method: "POST" },
    token,
  );
  return { ...data, correlationId };
};

export const fetchDocumentEdoEvents = (token: string, id: string) =>
  request<MarketplaceEdoEvent[]>(`/partner/documents/${id}/edo/events`, {}, token);

export const fetchOrderSettlement = (token: string, orderId: string) =>
  request<PaginatedResponse<MarketplaceSettlementLink>>(
    `/partner/settlements?source=MARKETPLACE&order_id=${encodeURIComponent(orderId)}`,
    {},
    token,
  );

export const fetchOrderSla = (token: string, id: string) =>
  request<MarketplaceOrderSlaResponse>(`/partner/orders/${id}/sla`, {}, token);

export const acceptOrder = async (token: string, id: string) => {
  const { data, correlationId } = await requestWithMeta<MarketplaceOrderActionResult>(
    `/partner/orders/${id}/accept`,
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

export const rejectOrder = async (token: string, id: string, reason: string) => {
  const { data, correlationId } = await requestWithMeta<MarketplaceOrderActionResult>(
    `/partner/orders/${id}/reject`,
    { method: "POST", body: JSON.stringify({ reason }) },
    token,
  );
  return { ...data, correlationId };
};

export const progressOrder = async (token: string, id: string, payload: { percent: number; message?: string }) => {
  const { data, correlationId } = await requestWithMeta<MarketplaceOrderActionResult>(
    `/partner/orders/${id}/progress`,
    { method: "POST", body: JSON.stringify(payload) },
    token,
  );
  return { ...data, correlationId };
};

export const completeOrder = async (token: string, id: string, payload?: { summary?: string }) => {
  const { data, correlationId } = await requestWithMeta<MarketplaceOrderActionResult>(
    `/partner/orders/${id}/complete`,
    { method: "POST", body: payload ? JSON.stringify(payload) : undefined },
    token,
  );
  return { ...data, correlationId };
};

export const failOrder = async (token: string, id: string, reason: string) => {
  const { data, correlationId } = await requestWithMeta<MarketplaceOrderActionResult>(
    `/partner/orders/${id}/fail`,
    { method: "POST", body: JSON.stringify({ reason }) },
    token,
  );
  return { ...data, correlationId };
};
