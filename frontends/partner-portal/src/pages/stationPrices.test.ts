import { describe, expect, it } from "vitest";
import { buildStationPricesPayload, mapPricesResponseToRows, validateStationPrice } from "./stationPrices";

describe("stationPrices helpers", () => {
  it("maps GET response to editable rows", () => {
    const rows = mapPricesResponseToRows({
      station_id: "station-1",
      currency: "RUB",
      items: [
        {
          product_code: "AI95",
          price: 56.1,
          currency: "RUB",
          valid_from: null,
          valid_to: null,
          updated_at: "2025-01-01T10:00:00Z",
        },
      ],
    });

    expect(rows).toEqual([
      {
        productCode: "AI95",
        price: "56.100",
        currency: "RUB",
        validFrom: null,
        validTo: null,
        updatedAt: "2025-01-01T10:00:00Z",
        updatedBy: null,
      },
    ]);
  });

  it("builds PUT payload with all rows", () => {
    const payload = buildStationPricesPayload([
      {
        productCode: "AI92",
        price: "52,125",
        currency: "RUB",
        validFrom: null,
        validTo: null,
      },
      {
        productCode: "DT",
        price: "63.4",
        currency: "RUB",
        validFrom: null,
        validTo: null,
      },
    ]);

    expect(payload).toEqual({
      source: "MANUAL",
      items: [
        { product_code: "AI92", price: 52.125, currency: "RUB", valid_from: null, valid_to: null },
        { product_code: "DT", price: 63.4, currency: "RUB", valid_from: null, valid_to: null },
      ],
    });
  });

  it("validates numeric price constraints", () => {
    expect(validateStationPrice("")).toContain("Укажите цену");
    expect(validateStationPrice("12.1234")).toContain("3 знаков");
    expect(validateStationPrice("0")).toContain("больше 0");
    expect(validateStationPrice("56.100")).toBeNull();
  });
});
