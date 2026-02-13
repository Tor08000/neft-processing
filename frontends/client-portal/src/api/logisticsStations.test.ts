import { describe, expect, it } from "vitest";
import { buildNearestStationsQuery, mapNearestStation } from "./logisticsStations";

describe("mapNearestStation", () => {
  it("maps API station into UI model", () => {
    const mapped = mapNearestStation({
      id: 12,
      name: "АЗС №1",
      address: "Москва, Тверская 1",
      lat: 55.75,
      lon: 37.61,
      distance_km: 1.42,
      nav_url: "https://maps.google.com/?q=55.75,37.61",
    });

    expect(mapped).toEqual({
      id: "12",
      name: "АЗС №1",
      address: "Москва, Тверская 1",
      lat: 55.75,
      lon: 37.61,
      distanceKm: 1.42,
      navUrl: "https://maps.google.com/?q=55.75,37.61",
    });
  });

  it("returns null when coordinates are missing", () => {
    expect(
      mapNearestStation({
        id: "x",
        name: "No coords",
        lat: null,
        lon: 37.61,
      }),
    ).toBeNull();
  });

  it("keeps navUrl when it is provided", () => {
    const mapped = mapNearestStation({
      id: "s-1",
      name: "АЗС",
      address: "Адрес",
      lat: 10,
      lon: 10,
      nav_url: "https://example.com/nav",
    });

    expect(mapped?.navUrl).toBe("https://example.com/nav");
  });
});

describe("buildNearestStationsQuery", () => {
  it("does not pass partner_id when partnerId is null", () => {
    const query = buildNearestStationsQuery({
      lat: 55.75,
      lon: 37.61,
      radiusKm: 5,
      partnerId: null,
      provider: "google",
    });

    expect(query.get("partner_id")).toBeNull();
  });

  it("passes partner_id when partnerId is set", () => {
    const query = buildNearestStationsQuery({
      lat: 55.75,
      lon: 37.61,
      radiusKm: 5,
      partnerId: 5,
      provider: "google",
    });

    expect(query.get("partner_id")).toBe("5");
  });

  it("changes radius in query", () => {
    const query = buildNearestStationsQuery({
      lat: 55.75,
      lon: 37.61,
      radiusKm: 20,
      provider: "google",
    });

    expect(query.get("radius_km")).toBe("20");
  });
});
