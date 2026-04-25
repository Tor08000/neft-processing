import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  buildGeoOverlaysQuery,
  buildGeoTilesQuery,
  fetchGeoStationsOverlay,
  tileToBounds,
} from "./geoAnalytics";
import { apiGet } from "./client";

vi.mock("./client", () => ({
  apiGet: vi.fn(),
}));

describe("geo analytics query builders", () => {
  it("builds tiles query with explicit bounds and metric", () => {
    const query = buildGeoTilesQuery({
      dateFrom: "2026-02-01T00:00:00.000Z",
      dateTo: "2026-02-02T00:00:00.000Z",
      bounds: { minLat: 55.5, minLon: 37.4, maxLat: 55.9, maxLon: 37.8 },
      zoom: 10,
      metric: "tx_count",
      limitTiles: 120,
    });

    const params = new URLSearchParams(query);
    expect(params.get("metric")).toBe("tx_count");
    expect(params.get("date_from")).toBe("2026-02-01");
    expect(params.get("date_to")).toBe("2026-02-02");
    expect(params.get("min_lat")).toBe("55.5");
    expect(params.get("min_lon")).toBe("37.4");
    expect(params.get("max_lat")).toBe("55.9");
    expect(params.get("max_lon")).toBe("37.8");
    expect(params.get("zoom")).toBe("10");
    expect(params.get("limit_tiles")).toBe("120");
  });

  it("builds overlays query with overlay kind", () => {
    const query = buildGeoOverlaysQuery({
      dateFrom: "2026-02-01T00:00:00.000Z",
      dateTo: "2026-02-02T00:00:00.000Z",
      bounds: { minLat: 40, minLon: 20, maxLat: 41, maxLon: 21 },
      zoom: 8,
      overlayKind: "HEALTH_OFFLINE",
    });

    const params = new URLSearchParams(query);
    expect(params.get("overlay_kind")).toBe("HEALTH_OFFLINE");
    expect(params.get("min_lat")).toBe("40");
    expect(params.get("min_lon")).toBe("20");
    expect(params.get("max_lat")).toBe("41");
    expect(params.get("max_lon")).toBe("21");
  });
});

describe("geo drill-down API", () => {
  beforeEach(() => {
    vi.mocked(apiGet).mockReset();
    vi.mocked(apiGet).mockResolvedValue({ items: [] });
  });

  it("uses explicit bounds for station overlay request", async () => {
    const tileBounds = tileToBounds({ tile_x: 553, tile_y: 321, zoom: 10 });

    await fetchGeoStationsOverlay({
      dateFrom: "2026-02-01T00:00:00.000Z",
      dateTo: "2026-02-02T00:00:00.000Z",
      bounds: tileBounds,
      metric: "amount_sum",
      limit: 200,
    });

    const calledUrl = vi.mocked(apiGet).mock.calls[0][0] as string;
    expect(calledUrl).toContain("/api/v1/geo/stations/overlay?");
    const queryString = calledUrl.split("?")[1];
    const params = new URLSearchParams(queryString);
    expect(params.get("metric")).toBe("amount_sum");
    expect(params.get("date_from")).toBe("2026-02-01");
    expect(params.get("date_to")).toBe("2026-02-02");
    expect(params.get("min_lat")).toBe(String(tileBounds.minLat));
    expect(params.get("min_lon")).toBe(String(tileBounds.minLon));
    expect(params.get("max_lat")).toBe(String(tileBounds.maxLat));
    expect(params.get("max_lon")).toBe(String(tileBounds.maxLon));
  });

  it("maps overlay kind to canonical station filters", async () => {
    await fetchGeoStationsOverlay({
      dateFrom: "2026-02-01",
      dateTo: "2026-02-02",
      bounds: { minLat: 55.5, minLon: 37.4, maxLat: 55.9, maxLon: 37.8 },
      metric: "risk_red_count",
      overlayKind: "RISK_RED",
    });

    let calledUrl = vi.mocked(apiGet).mock.calls[0][0] as string;
    let params = new URLSearchParams(calledUrl.split("?")[1]);
    expect(params.get("risk_zone")).toBe("RED");
    expect(params.get("health_status")).toBeNull();

    vi.mocked(apiGet).mockClear();

    await fetchGeoStationsOverlay({
      dateFrom: "2026-02-01",
      dateTo: "2026-02-02",
      bounds: { minLat: 55.5, minLon: 37.4, maxLat: 55.9, maxLon: 37.8 },
      metric: "tx_count",
      overlayKind: "HEALTH_DEGRADED",
    });

    calledUrl = vi.mocked(apiGet).mock.calls[0][0] as string;
    params = new URLSearchParams(calledUrl.split("?")[1]);
    expect(params.get("health_status")).toBe("DEGRADED");
    expect(params.get("risk_zone")).toBeNull();
  });
});
