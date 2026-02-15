import { request } from "./http";
import type {
  DriverDTO,
  PaginatedResponse,
  RouteDetail,
  TripDetail,
  TripDeviationsResponse,
  TripDeviationType,
  TripEta,
  TripListItem,
  TripSlaImpact,
  TripTrackingResponse,
  VehicleDTO,
} from "../types/logistics";

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

export type TripTrackingParams = {
  since?: string;
  limit?: number;
};

type RawTripFuelItem = {
  id?: string;
  fuel_tx_id?: string;
  ts?: string;
  vehicle_id?: string;
  driver_id?: string;
  liters?: number;
  amount?: number;
  station_name?: string;
  station?: string | null;
  lat?: number;
  lon?: number;
};

type RawTripFuelResponse = {
  trip_id?: string;
  items?: RawTripFuelItem[];
  totals?: { liters?: number; amount?: number };
  alerts?: import("../types/logistics").FuelAlertItem[];
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
  return request<PaginatedResponse<VehicleDTO>>(`/core/client/logistics/fleet${suffix}`, { method: "GET" }, { token });
}

export async function fetchDrivers(
  token: string,
  params?: LogisticsListParams,
): Promise<PaginatedResponse<DriverDTO>> {
  const suffix = buildQuery(params);
  return request<PaginatedResponse<DriverDTO>>(`/core/client/logistics/fleet/drivers${suffix}`, { method: "GET" }, { token });
}

export async function fetchTrips(
  token: string,
  params?: TripListParams,
): Promise<PaginatedResponse<TripListItem>> {
  const suffix = buildTripQuery(params);
  return request<PaginatedResponse<TripListItem>>(`/core/client/logistics/trips${suffix}`, { method: "GET" }, { token });
}

export async function fetchTripById(token: string, tripId: string): Promise<TripDetail> {
  return request<TripDetail>(`/core/client/logistics/trips/${tripId}`, { method: "GET" }, { token });
}

export async function fetchTripRoute(token: string, tripId: string): Promise<RouteDetail> {
  return request<RouteDetail>(`/core/client/logistics/trips/${tripId}/route`, { method: "GET" }, { token });
}

export async function fetchTripTracking(
  token: string,
  tripId: string,
  params?: TripTrackingParams,
): Promise<TripTrackingResponse> {
  const query = new URLSearchParams();
  if (params?.since) query.set("since", params.since);
  if (typeof params?.limit === "number") query.set("limit", String(params.limit));
  const suffix = query.toString();
  return request<TripTrackingResponse>(`/core/client/logistics/trips/${tripId}/tracking${suffix ? `?${suffix}` : ""}`, { method: "GET" }, { token });
}

export async function fetchTripPosition(token: string, tripId: string): Promise<TripTrackingResponse["last"]> {
  return request<TripTrackingResponse["last"]>(`/core/client/logistics/trips/${tripId}/position`, { method: "GET" }, { token });
}

export async function fetchTripEta(token: string, tripId: string): Promise<TripEta> {
  return request<TripEta>(`/core/client/logistics/trips/${tripId}/eta`, { method: "GET" }, { token });
}


export type TripDeviationsParams = {
  since?: string;
  until?: string;
  limit?: number;
  type?: TripDeviationType | "ALL";
};

export async function fetchTripDeviations(
  token: string,
  tripId: string,
  params?: TripDeviationsParams,
): Promise<TripDeviationsResponse> {
  const query = new URLSearchParams();
  if (params?.since) query.set("since", params.since);
  if (params?.until) query.set("until", params.until);
  if (typeof params?.limit === "number") query.set("limit", String(params.limit));
  if (params?.type && params.type !== "ALL") query.set("type", params.type);
  const suffix = query.toString();
  return request<TripDeviationsResponse>(`/core/client/logistics/trips/${tripId}/deviations${suffix ? `?${suffix}` : ""}`, { method: "GET" }, { token });
}

export async function fetchTripSlaImpact(token: string, tripId: string): Promise<TripSlaImpact> {
  return request<TripSlaImpact>(`/core/client/logistics/trips/${tripId}/sla-impact`, { method: "GET" }, { token });
}

export async function runFuelLinker(
  token: string,
  params: { date_from: string; date_to: string },
): Promise<{ processed: number; linked: number; unlinked: number; alerts_created: number }> {
  const query = new URLSearchParams(params);
  return request(`/core/client/logistics/fuel/linker:run?${query.toString()}`, { method: "POST" }, { token });
}

export async function fetchUnlinkedFuel(
  token: string,
  params: { date_from: string; date_to: string; limit?: number; offset?: number },
): Promise<import("../types/logistics").FuelUnlinkedItem[]> {
  const query = new URLSearchParams({ date_from: params.date_from, date_to: params.date_to });
  if (typeof params.limit === "number") query.set("limit", String(params.limit));
  if (typeof params.offset === "number") query.set("offset", String(params.offset));
  return request(`/core/client/logistics/fuel/unlinked?${query.toString()}`, { method: "GET" }, { token });
}

export async function fetchFuelAlerts(
  token: string,
  params: { date_from: string; date_to: string; type?: string; severity?: string; status?: string; limit?: number; offset?: number },
): Promise<import("../types/logistics").FuelAlertItem[]> {
  const query = new URLSearchParams({ date_from: params.date_from, date_to: params.date_to });
  if (params.type) query.set("type", params.type);
  if (params.severity) query.set("severity", params.severity);
  if (params.status) query.set("status", params.status);
  if (typeof params.limit === "number") query.set("limit", String(params.limit));
  if (typeof params.offset === "number") query.set("offset", String(params.offset));
  return request(`/core/client/logistics/fuel/alerts?${query.toString()}`, { method: "GET" }, { token });
}

export async function fetchFuelReport(
  token: string,
  params: { date_from: string; date_to: string; group_by: "trip" | "vehicle" | "driver"; period?: "day" | "week" | "month" },
): Promise<import("../types/logistics").FuelReportItem[]> {
  const query = new URLSearchParams({ date_from: params.date_from, date_to: params.date_to, group_by: params.group_by });
  if (params.period) query.set("period", params.period);
  return request(`/core/client/logistics/reports/fuel?${query.toString()}`, { method: "GET" }, { token });
}

export async function fetchTripFuel(token: string, tripId: string): Promise<import("../types/logistics").TripFuelResponse> {
  const response = await request<RawTripFuelResponse>(`/core/client/logistics/trips/${tripId}/fuel`, { method: "GET" }, { token });

  return {
    trip_id: response.trip_id ?? tripId,
    items: (response.items ?? []).reduce<import("../types/logistics").TripFuelItem[]>((acc, item) => {
      const fallbackId = item.id ?? item.fuel_tx_id;
      if (!fallbackId || !item.ts || typeof item.liters !== "number" || typeof item.amount !== "number") {
        return acc;
      }

      const normalized: import("../types/logistics").TripFuelItem = {
        id: String(fallbackId),
        ts: String(item.ts),
        vehicle_id: item.vehicle_id ?? "",
        driver_id: item.driver_id ?? "",
        liters: item.liters,
        amount: item.amount,
        station_name: item.station_name ?? item.station ?? "",
      };

      if (typeof item.lat === "number") {
        normalized.lat = item.lat;
      }

      if (typeof item.lon === "number") {
        normalized.lon = item.lon;
      }

      acc.push(normalized);
      return acc;
    }, []),
    totals: {
      liters: response.totals?.liters ?? 0,
      amount: response.totals?.amount ?? 0,
    },
    alerts: response.alerts ?? [],
  };
}
