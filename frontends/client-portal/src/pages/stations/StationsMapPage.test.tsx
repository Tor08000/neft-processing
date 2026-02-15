import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import { StationsMapPage } from "./StationsMapPage";

vi.mock("../../auth/AuthContext", () => ({
  useAuth: () => ({ user: { token: "token" } }),
}));

vi.mock("leaflet", () => ({
  default: {
    icon: () => ({}) as unknown,
    divIcon: () => ({}) as unknown,
  },
  icon: () => ({}),
  divIcon: () => ({}),
}));

vi.mock("react-leaflet", () => ({
  MapContainer: ({ children }: { children: ReactNode }) => <div data-testid="map">{children}</div>,
  Marker: ({ children, eventHandlers }: { children: ReactNode; eventHandlers?: { click?: () => void } }) => (
    <button type="button" onClick={() => eventHandlers?.click?.()}>
      {children}
    </button>
  ),
  Popup: ({ children }: { children: ReactNode }) => <span>{children}</span>,
  TileLayer: () => null,
  useMap: () => ({ flyTo: vi.fn(), getZoom: () => 12 }),
  useMapEvents: () => undefined,
}));

const stationsApi = vi.hoisted(() => ({
  fetchNearestStations: vi.fn(async () => [
    {
      id: "st-1",
      name: "Station 1",
      address: "Address 1",
      lat: 55.75,
      lon: 37.61,
      distanceKm: 1,
      navUrl: null,
      riskZone: "GREEN",
      riskZoneReason: null,
    },
    {
      id: "st-2",
      name: "Station 2",
      address: "Address 2",
      lat: 55.76,
      lon: 37.62,
      distanceKm: 2,
      navUrl: null,
      riskZone: "YELLOW",
      riskZoneReason: null,
    },
  ]),
  fetchStationById: vi.fn(async () => null),
}));

const pricesApi = vi.hoisted(() => ({
  getStationPrices: vi.fn(async (_token: string, stationId: string) => {
    if (stationId === "st-1") {
      return {
        items: [{ product_code: "AI95", price: 60, currency: "RUB", updated_at: "2024-01-01T00:00:00Z", source: "ops" }],
      };
    }
    return { items: [{ product_code: "AI92", price: 58, currency: "RUB", updated_at: "2024-01-01T00:01:00Z", source: "ops" }] };
  }),
}));

vi.mock("../../api/stationsNearest", () => stationsApi);
vi.mock("../../api/fuelStationsPrices", () => pricesApi);

describe("StationsMapPage prices", () => {
  it("fetches prices on active station and uses cache on reselect", async () => {
    render(
      <MemoryRouter>
        <StationsMapPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(pricesApi.getStationPrices).toHaveBeenCalledWith("token", "st-1"));

    fireEvent.click(screen.getAllByRole("button", { name: /Station 2/i })[1]);
    await waitFor(() => expect(pricesApi.getStationPrices).toHaveBeenCalledWith("token", "st-2"));

    const callsBeforeReselect = pricesApi.getStationPrices.mock.calls.length;
    fireEvent.click(screen.getAllByRole("button", { name: /Station 1/i })[1]);

    await waitFor(() => expect(screen.getByText("60 RUB")).toBeInTheDocument());
    expect(pricesApi.getStationPrices).toHaveBeenCalledTimes(callsBeforeReselect);
  });

  it("shows empty and error states with retry", async () => {
    pricesApi.getStationPrices.mockImplementationOnce(async () => ({ items: [] }));

    render(
      <MemoryRouter>
        <StationsMapPage />
      </MemoryRouter>,
    );

    await screen.findByText("Цены не опубликованы");

    pricesApi.getStationPrices.mockRejectedValueOnce(new Error("boom"));
    fireEvent.click(screen.getByRole("button", { name: "Обновить цены" }));
    await screen.findByText("Не удалось загрузить цены");

    pricesApi.getStationPrices.mockResolvedValueOnce({
      items: [{ product_code: "DT", price: 70, currency: "RUB", updated_at: "2024-01-01T00:02:00Z", source: null }],
    });
    fireEvent.click(screen.getByRole("button", { name: "Повторить" }));

    await screen.findByText("70 RUB");
  });
});
