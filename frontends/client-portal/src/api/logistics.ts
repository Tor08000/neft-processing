import { request } from "./http";
import type { DriverDTO, PaginatedResponse, RouteDetail, TripDetail, TripListItem, VehicleDTO } from "../types/logistics";

export type LogisticsListParams = {
  status?: string;
  q?: string;
  limit?: number;
  offset?: number;
};

export type TripListParams = LogisticsListParams & {
  date_from?: string;
  date_to?: string;
  vehicle_id?: string;
  driver_id?: string;
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

const buildTripQuery = (params?: TripListParams): string => {
  if (!params) return "";
  const query = new URLSearchParams();
  if (params.status) query.set("status", params.status);
  if (params.q) query.set("q", params.q);
  if (params.date_from) query.set("date_from", params.date_from);
  if (params.date_to) query.set("date_to", params.date_to);
  if (params.vehicle_id) query.set("vehicle_id", params.vehicle_id);
  if (params.driver_id) query.set("driver_id", params.driver_id);
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

export async function fetchTrips(
  token: string,
  params?: TripListParams,
): Promise<PaginatedResponse<TripListItem>> {
  const suffix = buildTripQuery(params);
  return request<PaginatedResponse<TripListItem>>(`/v1/logistics/trips${suffix}`, { method: "GET" }, { token });
}

export async function fetchTripById(token: string, tripId: string): Promise<TripDetail> {
  return request<TripDetail>(`/v1/logistics/trips/${tripId}`, { method: "GET" }, { token });
}

export async function fetchTripRoute(token: string, tripId: string): Promise<RouteDetail> {
  return request<RouteDetail>(`/v1/logistics/trips/${tripId}/route`, { method: "GET" }, { token });
}
