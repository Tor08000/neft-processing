import { apiGet } from "./client";

export type GeoMetric = "tx_count" | "amount_sum" | "declined_count" | "risk_red_count";
export type GeoOverlayKind = "RISK_RED" | "HEALTH_OFFLINE" | "HEALTH_DEGRADED";

export interface GeoBounds {
  minLat: number;
  minLon: number;
  maxLat: number;
  maxLon: number;
}

export interface GeoTile {
  tile_x: number;
  tile_y: number;
  zoom: number;
  value: number;
}

export interface GeoStation {
  id?: string;
  station_id?: string;
  name: string;
  address?: string | null;
  value?: number | null;
  risk_zone?: string | null;
  health_status?: string | null;
}

interface GeoTilesResponse {
  items?: GeoTile[];
  tiles?: GeoTile[];
}

interface GeoStationsResponse {
  items?: GeoStation[];
  stations?: GeoStation[];
}

export interface GeoTilesParams {
  dateFrom: string;
  dateTo: string;
  bounds: GeoBounds;
  zoom: number;
  limitTiles?: number;
}

export interface GeoStationsParams {
  dateFrom: string;
  dateTo: string;
  bounds: GeoBounds;
  metric: GeoMetric;
  limit?: number;
  overlayKind?: GeoOverlayKind;
}

const toApiDate = (value: string) => {
  if (/^\d{4}-\d{2}-\d{2}$/.test(value.trim())) {
    return value.trim();
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value.slice(0, 10);
  }
  return parsed.toISOString().slice(0, 10);
};

const createBaseParams = (params: GeoTilesParams) => {
  const query = new URLSearchParams();
  query.set("date_from", toApiDate(params.dateFrom));
  query.set("date_to", toApiDate(params.dateTo));
  query.set("min_lat", String(params.bounds.minLat));
  query.set("min_lon", String(params.bounds.minLon));
  query.set("max_lat", String(params.bounds.maxLat));
  query.set("max_lon", String(params.bounds.maxLon));
  query.set("zoom", String(params.zoom));
  query.set("limit_tiles", String(params.limitTiles ?? 500));
  return query;
};

export const buildGeoTilesQuery = (params: GeoTilesParams & { metric: GeoMetric }): string => {
  const query = createBaseParams(params);
  query.set("metric", params.metric);
  return query.toString();
};

export const buildGeoOverlaysQuery = (params: GeoTilesParams & { overlayKind: GeoOverlayKind }): string => {
  const query = createBaseParams(params);
  query.set("overlay_kind", params.overlayKind);
  return query.toString();
};

export const tileToBounds = (tile: Pick<GeoTile, "tile_x" | "tile_y" | "zoom">): GeoBounds => {
  const n = 2 ** tile.zoom;
  const minLon = (tile.tile_x / n) * 360 - 180;
  const maxLon = ((tile.tile_x + 1) / n) * 360 - 180;

  const maxLatRad = Math.atan(Math.sinh(Math.PI * (1 - (2 * tile.tile_y) / n)));
  const minLatRad = Math.atan(Math.sinh(Math.PI * (1 - (2 * (tile.tile_y + 1)) / n)));

  return {
    minLat: (minLatRad * 180) / Math.PI,
    minLon,
    maxLat: (maxLatRad * 180) / Math.PI,
    maxLon,
  };
};

export async function fetchGeoTiles(params: GeoTilesParams & { metric: GeoMetric }) {
  const query = buildGeoTilesQuery(params);
  const response = await apiGet<GeoTilesResponse>(`/api/v1/geo/tiles?${query}`);
  return response.items ?? response.tiles ?? [];
}

export async function fetchGeoOverlayTiles(params: GeoTilesParams & { overlayKind: GeoOverlayKind }) {
  const query = buildGeoOverlaysQuery(params);
  const response = await apiGet<GeoTilesResponse>(`/api/v1/geo/tiles/overlays?${query}`);
  return response.items ?? response.tiles ?? [];
}

export async function fetchGeoStationsOverlay(params: GeoStationsParams) {
  const query = new URLSearchParams();
  query.set("date_from", toApiDate(params.dateFrom));
  query.set("date_to", toApiDate(params.dateTo));
  query.set("min_lat", String(params.bounds.minLat));
  query.set("min_lon", String(params.bounds.minLon));
  query.set("max_lat", String(params.bounds.maxLat));
  query.set("max_lon", String(params.bounds.maxLon));
  query.set("metric", params.metric);
  query.set("limit", String(params.limit ?? 200));
  if (params.overlayKind === "HEALTH_OFFLINE") {
    query.set("health_status", "OFFLINE");
  }
  if (params.overlayKind === "HEALTH_DEGRADED") {
    query.set("health_status", "DEGRADED");
  }
  if (params.overlayKind === "RISK_RED") {
    query.set("risk_zone", "RED");
  }
  const response = await apiGet<GeoStationsResponse>(`/api/v1/geo/stations/overlay?${query.toString()}`);
  return response.items ?? response.stations ?? [];
}
