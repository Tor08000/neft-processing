import { afterEach, describe, expect, it, vi } from "vitest";
import { importFuelStationPrices } from "./partner";

describe("partner fuel station prices api", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("calls CSV import endpoint with multipart form data", async () => {
    const fetchMock = vi.fn(async () =>
      new Response(JSON.stringify({ station_id: "station-1", inserted: 1, updated: 0, skipped: 0, errors: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    await importFuelStationPrices("token-1", "station-1", new File(["product_code,price\nAI95,56.1"], "prices.csv"));

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, request] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/api/v1/partner/fuel/stations/station-1/prices/import");
    expect(request.method).toBe("POST");
    expect(request.body).toBeInstanceOf(FormData);
  });
});
