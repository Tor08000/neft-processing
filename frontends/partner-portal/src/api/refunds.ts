import { request, requestWithMeta } from "./http";
import type { PaginatedResponse } from "./partner";
import type { RefundActionResult, RefundRequest } from "../types/marketplace";

export interface RefundFilters {
  status?: string;
  from?: string;
  to?: string;
}

const toQuery = (filters: RefundFilters): string => {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value) {
      params.set(key, value);
    }
  });
  const query = params.toString();
  return query ? `?${query}` : "";
};

export const fetchRefunds = (token: string, filters: RefundFilters = {}) =>
  request<PaginatedResponse<RefundRequest>>(`/partner/refunds${toQuery(filters)}`, {}, token);

export const fetchRefund = (token: string, id: string) => request<RefundRequest>(`/partner/refunds/${id}`, {}, token);

export const approveRefund = async (token: string, id: string) => {
  const { data, correlationId } = await requestWithMeta<RefundActionResult>(
    `/partner/refunds/${id}/approve`,
    { method: "POST" },
    token,
  );
  return { ...data, correlationId };
};

export const denyRefund = async (token: string, id: string) => {
  const { data, correlationId } = await requestWithMeta<RefundActionResult>(
    `/partner/refunds/${id}/deny`,
    { method: "POST" },
    token,
  );
  return { ...data, correlationId };
};
