import { request } from "./http";
import type { AuthSession } from "./types";
import type { ServiceSloBreachListResponse, ServiceSloListResponse, ServiceSloService, ServiceSloWindow } from "../types/slo";

const withToken = (user: AuthSession | null) => ({ token: user?.token, base: "core_root" as const });

export const fetchServiceSlos = (user: AuthSession | null) =>
  request<ServiceSloListResponse>("/client/slo", { method: "GET" }, withToken(user));

export const fetchServiceSloBreaches = (
  user: AuthSession | null,
  params: { service?: ServiceSloService; window?: ServiceSloWindow } = {},
) => {
  const search = new URLSearchParams();
  if (params.service) {
    search.set("service", params.service);
  }
  if (params.window) {
    search.set("window", params.window);
  }
  const query = search.toString();
  const suffix = query ? `?${query}` : "";
  return request<ServiceSloBreachListResponse>(`/client/slo/breaches${suffix}`, { method: "GET" }, withToken(user));
};
