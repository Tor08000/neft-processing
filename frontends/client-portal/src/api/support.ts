import { request } from "./http";
import type { AuthSession } from "./types";
import type { SupportRequestCreatePayload, SupportRequestDetail, SupportRequestListResponse } from "../types/support";

const withToken = (user: AuthSession | null): string | undefined => user?.token;

export interface SupportRequestFilters {
  status?: string;
  subject_type?: string;
  from?: string;
  to?: string;
  limit?: number;
  offset?: number;
}

export const createSupportRequest = (payload: SupportRequestCreatePayload, user: AuthSession | null) =>
  request<SupportRequestDetail>("/support/requests", { method: "POST", body: JSON.stringify(payload) }, withToken(user));

export const fetchSupportRequests = (user: AuthSession | null, filters: SupportRequestFilters = {}) => {
  const search = new URLSearchParams();
  if (filters.status) search.set("status", filters.status);
  if (filters.subject_type) search.set("subject_type", filters.subject_type);
  if (filters.from) search.set("from", filters.from);
  if (filters.to) search.set("to", filters.to);
  if (filters.limit) search.set("limit", String(filters.limit));
  if (filters.offset) search.set("offset", String(filters.offset));
  const query = search.toString();
  const path = query ? `/support/requests?${query}` : "/support/requests";
  return request<SupportRequestListResponse>(path, { method: "GET" }, withToken(user));
};

export const fetchSupportRequest = (requestId: string, user: AuthSession | null) =>
  request<SupportRequestDetail>(`/support/requests/${requestId}`, { method: "GET" }, withToken(user));
