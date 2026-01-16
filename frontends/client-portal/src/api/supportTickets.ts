import { request } from "./http";
import type { AuthSession } from "./types";
import type {
  SupportTicketCommentPayload,
  SupportTicketCreatePayload,
  SupportTicketDetail,
  SupportTicketListResponse,
} from "../types/supportTickets";

const withToken = (user: AuthSession | null): string | undefined => user?.token;

export interface SupportTicketFilters {
  status?: string;
  limit?: number;
  cursor?: string;
}

export const createSupportTicket = (payload: SupportTicketCreatePayload, user: AuthSession | null) =>
  request<SupportTicketDetail>(
    "/client/support/tickets",
    { method: "POST", body: JSON.stringify(payload) },
    withToken(user),
  );

export const fetchSupportTickets = (user: AuthSession | null, filters: SupportTicketFilters = {}) => {
  const search = new URLSearchParams();
  if (filters.status) search.set("status", filters.status);
  if (filters.limit) search.set("limit", String(filters.limit));
  if (filters.cursor) search.set("cursor", filters.cursor);
  const query = search.toString();
  const path = query ? `/client/support/tickets?${query}` : "/client/support/tickets";
  return request<SupportTicketListResponse>(path, { method: "GET" }, withToken(user));
};

export const fetchSupportTicket = (ticketId: string, user: AuthSession | null) =>
  request<SupportTicketDetail>(`/client/support/tickets/${ticketId}`, { method: "GET" }, withToken(user));

export const createSupportTicketComment = (
  ticketId: string,
  payload: SupportTicketCommentPayload,
  user: AuthSession | null,
) =>
  request<SupportTicketDetail>(
    `/client/support/tickets/${ticketId}/comments`,
    { method: "POST", body: JSON.stringify(payload) },
    withToken(user),
  );

export const closeSupportTicket = (ticketId: string, user: AuthSession | null) =>
  request<SupportTicketDetail>(`/client/support/tickets/${ticketId}/close`, { method: "POST" }, withToken(user));
