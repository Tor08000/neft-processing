import { request } from "./http";

export type NearestStationsParams = {
  lat: number;
  lon: number;
  radiusKm: number;
  partnerId?: number | null;
  limit?: number;
  provider?: "google" | "yandex" | "apple";
};

export type RawNearestStation = {
  id?: string | number;
  name?: string | null;
  address?: string | null;
  lat?: number | null;
  lon?: number | null;
  distance_km?: number | null;
  nav_url?: string | null;
};

export type StationMapItem = {
  id: string;
  name: string;
  address: string;
  lat: number;
  lon: number;
  distanceKm: number | null;
  navUrl: string | null;
};

const asNumber = (value: unknown): number | null => {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return null;
  }
  return value;
};

export function mapNearestStation(raw: RawNearestStation): StationMapItem | null {
  const lat = asNumber(raw.lat);
  const lon = asNumber(raw.lon);
  if (lat === null || lon === null) {
    return null;
  }

  return {
    id: String(raw.id ?? `${lat}:${lon}`),
    name: raw.name?.trim() || "Без названия",
    address: raw.address?.trim() || "Адрес не указан",
    lat,
    lon,
    distanceKm: asNumber(raw.distance_km),
    navUrl: raw.nav_url?.trim() || null,
  };
}

export async function fetchNearestStations(token: string, params: NearestStationsParams): Promise<StationMapItem[]> {
  const query = buildNearestStationsQuery(params);

  const response = await request<RawNearestStation[]>(`/v1/fuel/stations/nearest?${query.toString()}`, { method: "GET" }, { token });

  return (response ?? []).map(mapNearestStation).filter((item): item is StationMapItem => Boolean(item));
}

export function buildNearestStationsQuery(params: NearestStationsParams): URLSearchParams {
  const query = new URLSearchParams({
    lat: String(params.lat),
    lon: String(params.lon),
    radius_km: String(params.radiusKm),
    limit: String(params.limit ?? 50),
    provider: params.provider ?? "google",
  });

  if (typeof params.partnerId === "number") {
    query.set("partner_id", String(params.partnerId));
  }

  return query;
}


export async function fetchStationById(token: string, stationId: string, provider: "google" | "yandex" | "apple" = "google"): Promise<StationMapItem | null> {
  const raw = await request<RawNearestStation>(`/v1/fuel/stations/${encodeURIComponent(stationId)}`, { method: "GET" }, { token });
  if (!raw) return null;
  const mapped = mapNearestStation(raw);
  if (!mapped) return null;
  if (!mapped.navUrl && mapped.lat != null && mapped.lon != null) {
    mapped.navUrl = `${provider === "yandex" ? "https://yandex.ru/maps/?rtext=~" : provider === "apple" ? "http://maps.apple.com/?daddr=" : "https://www.google.com/maps/dir/?api=1&destination="}${mapped.lat},${mapped.lon}`;
  }
  return mapped;
}
