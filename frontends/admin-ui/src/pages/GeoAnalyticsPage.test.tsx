import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../api/http";
import GeoAnalyticsPage from "./GeoAnalyticsPage";
import * as geoApi from "../api/geoAnalytics";

vi.mock("../api/geoAnalytics", () => ({
  fetchGeoTiles: vi.fn(),
  fetchGeoOverlayTiles: vi.fn(),
  fetchGeoStationsOverlay: vi.fn(),
  tileToBounds: vi.fn((tile: { tile_x: number; tile_y: number; zoom: number }) => ({
    minLat: 55.6,
    minLon: 37.35,
    maxLat: 55.75,
    maxLon: 37.55,
  })),
}));

describe("GeoAnalyticsPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    (geoApi.fetchGeoTiles as ReturnType<typeof vi.fn>).mockResolvedValue([]);
    (geoApi.fetchGeoOverlayTiles as ReturnType<typeof vi.fn>).mockResolvedValue([]);
    (geoApi.fetchGeoStationsOverlay as ReturnType<typeof vi.fn>).mockResolvedValue([]);
    (geoApi.tileToBounds as ReturnType<typeof vi.fn>).mockImplementation((tile: { tile_x: number; tile_y: number; zoom: number }) => ({
      minLat: 55.6,
      minLon: 37.35,
      maxLat: 55.75,
      maxLon: 37.55,
    }));
  });

  it("renders a structured geo layer error instead of a raw backend payload", async () => {
    (geoApi.fetchGeoTiles as ReturnType<typeof vi.fn>).mockRejectedValue(
      new ApiError(
        JSON.stringify({
          error: "internal_error",
          message: "Internal Server Error",
          request_id: "req-geo-1",
        }),
        500,
        "req-geo-1",
        "corr-geo-1",
        "internal_error",
      ),
    );

    render(<GeoAnalyticsPage />);

    expect(await screen.findByText("Geo layer unavailable")).toBeInTheDocument();
    expect(screen.getByText("Geo tiles owner route returned an internal error. Retry or inspect request metadata below.")).toBeInTheDocument();
    expect(screen.getByText(/request_id: req-geo-1/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });

  it("distinguishes first-use and selected-tile empty drill-down states", async () => {
    (geoApi.fetchGeoTiles as ReturnType<typeof vi.fn>).mockResolvedValue([
      { tile_x: 10, tile_y: 20, zoom: 8, value: 5 },
    ]);

    render(<GeoAnalyticsPage />);

    expect(await screen.findByText("Choose a tile to inspect stations")).toBeInTheDocument();

    fireEvent.click(screen.getByTitle("10/20/8"));

    expect(await screen.findByText("No stations in the selected tile")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Открыть станцию" })).not.toBeInTheDocument();
    await waitFor(() => expect(geoApi.fetchGeoStationsOverlay).toHaveBeenCalledTimes(1));
  });
});
