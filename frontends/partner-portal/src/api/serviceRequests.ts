import { request } from "./http";
import type { AuthSession } from "./types";

export type ServiceRequestItem = {
  id: string;
  client_id: string;
  partner_id: string;
  service_id: string;
  status: string;
  created_at?: string;
  payload?: {
    description?: string;
  };
};

const withToken = (user: AuthSession | null) => ({ token: user?.token, base: "core" as const });

export const listPartnerServiceRequests = (user: AuthSession | null) =>
  request<ServiceRequestItem[]>("/partner/services/requests", { method: "GET" }, withToken(user));

export const acceptPartnerServiceRequest = (user: AuthSession | null, id: string) =>
  request<{ id: string; status: string }>(`/partner/services/requests/${id}/accept`, { method: "POST" }, withToken(user));

export const rejectPartnerServiceRequest = (user: AuthSession | null, id: string) =>
  request<{ id: string; status: string }>(`/partner/services/requests/${id}/reject`, { method: "POST" }, withToken(user));

export const completePartnerServiceRequest = (user: AuthSession | null, id: string) =>
  request<{ id: string; status: string }>(`/partner/services/requests/${id}/complete`, { method: "POST" }, withToken(user));
