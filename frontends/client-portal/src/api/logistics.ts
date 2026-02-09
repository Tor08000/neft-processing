import { request } from "./http";
import type { DriverDTO, PaginatedResponse, VehicleDTO } from "../types/logistics";

export type LogisticsListParams = {
  status?: string;
  q?: string;
  limit?: number;
  offset?: number;
};

const buildQuery = (params?: LogisticsListParams): string => {
  if (!params) return "";
  const query = new URLSearchParams();
  if (params.status) query.set("status", params.status);
  if (params.q) query.set("q", params.q);
  if (typeof params.limit === "number") query.set("limit", String(params.limit));
  if (typeof params.offset === "number") query.set("offset", String(params.offset));
  const suffix = query.toString();
  return suffix ? `?${suffix}` : "";
};

export async function fetchVehicles(
  token: string,
  params?: LogisticsListParams,
): Promise<PaginatedResponse<VehicleDTO>> {
  const suffix = buildQuery(params);
  return request<PaginatedResponse<VehicleDTO>>(`/v1/logistics/vehicles${suffix}`, { method: "GET" }, { token });
}

export async function fetchDrivers(
  token: string,
  params?: LogisticsListParams,
): Promise<PaginatedResponse<DriverDTO>> {
  const suffix = buildQuery(params);
  return request<PaginatedResponse<DriverDTO>>(`/v1/logistics/drivers${suffix}`, { method: "GET" }, { token });
}
