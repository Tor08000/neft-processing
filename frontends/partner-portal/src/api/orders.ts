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
  MarketplaceOrderSettlementBreakdown,
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

type OrdersListResponse = PaginatedResponse<Record<string, unknown>> & {
  limit?: number;
  offset?: number;
};

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

const mapOrderItem = (item: Record<string, unknown>) => ({
  offerId: String(item.offer_id ?? item.offerId ?? ""),
  subjectType: (item.subject_type ?? item.subjectType ?? null) as string | null,
  subjectId: (item.subject_id ?? item.subjectId ?? null) as string | null,
  title: (item.title_snapshot ?? item.title ?? null) as string | null,
  qty: Number(item.qty ?? 0),
  unitPrice: Number(item.unit_price ?? item.unitPrice ?? 0),
  amount: Number(item.line_amount ?? item.amount ?? 0),
});

const mapProof = (proof: Record<string, unknown>) => ({
  id: String(proof.id ?? ""),
  orderId: String(proof.order_id ?? proof.orderId ?? ""),
  kind: String(proof.kind ?? ""),
  attachmentId: String(proof.attachment_id ?? proof.attachmentId ?? ""),
  note: (proof.note ?? null) as string | null,
  createdAt: String(proof.created_at ?? proof.createdAt ?? ""),
});

const mapOrder = (order: Record<string, unknown>): MarketplaceOrder => {
  const items = (order.lines ?? order.items ?? []) as Record<string, unknown>[];
  const proofs = (order.proofs ?? []) as Record<string, unknown>[];
  const mappedItems = items.map(mapOrderItem);
  return {
    id: String(order.id ?? ""),
    clientId: String(order.client_id ?? order.clientId ?? ""),
    partnerId: String(order.partner_id ?? order.partnerId ?? ""),
    items: mappedItems,
    itemsCount: Number(order.items_count ?? order.itemsCount ?? mappedItems.length ?? 0),
    status: String(order.status ?? "CREATED") as MarketplaceOrder["status"],
    paymentStatus: (order.payment_status ?? order.paymentStatus ?? null) as MarketplaceOrder["paymentStatus"],
    paymentMethod: (order.payment_method ?? order.paymentMethod ?? null) as string | null,
    subtotalAmount: (order.subtotal_amount ?? order.subtotalAmount ?? null) as number | null,
    discountAmount: (order.discount_amount ?? order.discountAmount ?? null) as number | null,
    totalAmount: (order.total_amount ?? order.totalAmount ?? null) as number | null,
    currency: (order.currency ?? null) as string | null,
    serviceTitle: (order.service_title ??
      order.serviceTitle ??
      mappedItems[0]?.title ??
      null) as string | null,
    documents: (order.documents ?? null) as MarketplaceOrder["documents"],
    documentsStatus: (order.documents_status ?? order.documentsStatus ?? null) as string | null,
    proofs: proofs.length ? proofs.map(mapProof) : null,
    correlationId: (order.correlation_id ?? order.correlationId ?? null) as string | null,
    slaResponseDueAt: (order.sla_response_due_at ?? order.slaResponseDueAt ?? null) as string | null,
    slaCompletionDueAt: (order.sla_completion_due_at ?? order.slaCompletionDueAt ?? null) as string | null,
    slaResponseRemainingSeconds:
      (order.sla_response_remaining_seconds ?? order.slaResponseRemainingSeconds ?? null) as number | null,
    slaCompletionRemainingSeconds:
      (order.sla_completion_remaining_seconds ?? order.slaCompletionRemainingSeconds ?? null) as number | null,
    createdAt: String(order.created_at ?? order.createdAt ?? ""),
    updatedAt: String(order.updated_at ?? order.updatedAt ?? ""),
  };
};

const mapOrderEvent = (event: Record<string, unknown>): MarketplaceOrderEvent => ({
  id: String(event.id ?? ""),
  type: String(event.event_type ?? event.type ?? ""),
  status: (event.after_status ?? event.status ?? null) as string | null,
  note: (event.note ?? null) as string | null,
  actor: (event.actor_type ?? event.actor ?? null) as string | null,
  createdAt: String(event.created_at ?? event.createdAt ?? ""),
  reasonCode: (event.reason_code ?? event.reasonCode ?? null) as string | null,
  comment: (event.comment ?? null) as string | null,
});

export const fetchOrders = (token: string, filters: OrderFilters = {}) =>
  request<OrdersListResponse>(`/v1/marketplace/partner/orders${toQuery(filters)}`, {}, token).then((data) => {
    const limit = Number(data.limit ?? 0) || 0;
    const offset = Number(data.offset ?? 0) || 0;
    const pageSize = limit || (data.items ?? []).length || 1;
    const page = pageSize ? Math.floor(offset / pageSize) + 1 : 1;
    return {
      ...data,
      page,
      pageSize,
      items: (data.items ?? []).map((item) => mapOrder(item)),
    };
  });

export const fetchOrder = (token: string, id: string) =>
  request<Record<string, unknown>>(`/v1/marketplace/partner/orders/${id}`, {}, token).then((data) =>
    mapOrder(data),
  );

export const fetchOrderEvents = (token: string, id: string) =>
  request<Record<string, unknown>[]>(`/v1/marketplace/partner/orders/${id}/events`, {}, token).then((data) =>
    data.map((event) => mapOrderEvent(event)),
  );

export const fetchOrderDocuments = (token: string, id: string) =>
  request<MarketplaceDocumentDetails[]>(`/v1/marketplace/partner/orders/${id}/documents`, {}, token);

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

export const fetchOrderSettlementBreakdown = (token: string, orderId: string) =>
  request<MarketplaceOrderSettlementBreakdown>(`/v1/marketplace/partner/orders/${orderId}/settlement`, {}, token);

export const fetchOrderSla = (token: string, id: string) =>
  request<MarketplaceOrderSlaResponse>(`/v1/marketplace/partner/orders/${id}/sla`, {}, token);

export const confirmOrder = async (token: string, id: string) => {
  const { data, correlationId } = await requestWithMeta<MarketplaceOrderActionResult>(
    `/v1/marketplace/partner/orders/${id}:confirm`,
    { method: "POST" },
    token,
  );
  return { ...data, correlationId };
};

export const declineOrder = async (token: string, id: string, reason_code: string, comment: string) => {
  const { data, correlationId } = await requestWithMeta<MarketplaceOrderActionResult>(
    `/v1/marketplace/partner/orders/${id}:decline`,
    { method: "POST", body: JSON.stringify({ reason_code, comment }) },
    token,
  );
  return { ...data, correlationId };
};

export const uploadOrderProof = async (
  token: string,
  id: string,
  payload: { attachment_id: string; kind: string; note?: string },
) => {
  const { data, correlationId } = await requestWithMeta<Record<string, unknown>>(
    `/v1/marketplace/partner/orders/${id}/proofs`,
    { method: "POST", body: JSON.stringify(payload) },
    token,
  );
  return { ...mapProof(data), correlationId };
};

export const completeOrder = async (token: string, id: string, payload?: { comment?: string }) => {
  const { data, correlationId } = await requestWithMeta<MarketplaceOrderActionResult>(
    `/v1/marketplace/partner/orders/${id}:complete`,
    { method: "POST", body: payload ? JSON.stringify(payload) : undefined },
    token,
  );
  return { ...data, correlationId };
};
