import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  buildGeoOverlaysQuery,
  buildGeoTilesQuery,
  fetchGeoStationsOverlay,
  tileToBounds,
} from "./geoAnalytics";
import { request } from "./http";

vi.mock("./http", () => ({
  request: vi.fn(),
}));

describe("geo analytics query builders", () => {
  it("builds tiles query with bbox and metric", () => {
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
    expect(params.get("bbox")).toBe("37.4,55.5,37.8,55.9");
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
    expect(params.get("bbox")).toBe("20,40,21,41");
  });
});

describe("geo drill-down API", () => {
  beforeEach(() => {
    vi.mocked(request).mockReset();
    vi.mocked(request).mockResolvedValue({ stations: [] });
  });

  it("uses tile bbox for station overlay request", async () => {
    const tileBounds = tileToBounds({ tile_x: 553, tile_y: 321, zoom: 10 });

    await fetchGeoStationsOverlay({
      dateFrom: "2026-02-01T00:00:00.000Z",
      dateTo: "2026-02-02T00:00:00.000Z",
      bounds: tileBounds,
      metric: "amount_sum",
      limit: 200,
    });

    const calledUrl = vi.mocked(request).mock.calls[0][0] as string;
    expect(calledUrl).toContain("/api/v1/geo/stations/overlay?");
    const queryString = calledUrl.split("?")[1];
    const params = new URLSearchParams(queryString);
    expect(params.get("metric")).toBe("amount_sum");
    expect(params.get("bbox")).toBe(
      `${tileBounds.minLon},${tileBounds.minLat},${tileBounds.maxLon},${tileBounds.maxLat}`,
    );
  });
});
