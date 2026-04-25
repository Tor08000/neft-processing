import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getClientFeatures, listClients, subscriptionCfoExplain, updateSubscription } from "./crm";

const buildResponse = (payload: unknown, init: ResponseInit = {}) =>
  new Response(JSON.stringify(payload), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init,
  });

describe("crm api", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    global.fetch = originalFetch;
  });

  it("sends X-CRM-Version and normalizes client lists", async () => {
    const fetchMock = global.fetch as ReturnType<typeof vi.fn>;
    fetchMock.mockResolvedValue(
      buildResponse([
        {
          id: "client-1",
          tenant_id: 1,
          legal_name: "Client",
          country: "RU",
          timezone: "Europe/Moscow",
          status: "ACTIVE",
          created_at: "2026-01-01T10:00:00Z",
          updated_at: "2026-01-01T10:00:00Z",
        },
      ]),
    );

    const response = await listClients("token-1", { status: "ACTIVE" });

    expect(response.items).toHaveLength(1);
    expect(response.items[0]?.client_id).toBe("client-1");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/core/v1/admin/crm/clients?status=ACTIVE",
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({
          Authorization: "Bearer token-1",
          "Content-Type": "application/json",
          "X-CRM-Version": "1",
        }),
      }),
    );
  });

  it("maps feature flag arrays into a truthy record", async () => {
    const fetchMock = global.fetch as ReturnType<typeof vi.fn>;
    fetchMock.mockResolvedValue(
      buildResponse([
        { feature: "FUEL_ENABLED", enabled: true },
        { feature: "DOCUMENTS_ENABLED", enabled: false },
      ]),
    );

    const response = await getClientFeatures("token-1", "client-1");

    expect(response).toEqual({
      FUEL_ENABLED: true,
      DOCUMENTS_ENABLED: false,
    });
  });

  it("calls subscription CFO explain with GET", async () => {
    const fetchMock = global.fetch as ReturnType<typeof vi.fn>;
    fetchMock.mockResolvedValue(buildResponse({ totals: { amount_minor: 1000 } }));

    await subscriptionCfoExplain("token-1", "sub-1", { period_id: "2026-01" });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/core/v1/admin/crm/subscriptions/sub-1/cfo-explain?period_id=2026-01",
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({ "X-CRM-Version": "1" }),
      }),
    );
  });

  it("strips create-only subscription fields from PATCH payload", async () => {
    const fetchMock = global.fetch as ReturnType<typeof vi.fn>;
    fetchMock.mockResolvedValue(
      buildResponse({
        id: "sub-1",
        tenant_id: 1,
        client_id: "client-1",
        tariff_plan_id: "tariff-1",
        status: "ACTIVE",
        billing_cycle: "MONTHLY",
        billing_day: 5,
        started_at: "2026-01-01T00:00:00Z",
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      }),
    );

    await updateSubscription("token-1", "sub-1", {
      tenant_id: 77,
      tariff_plan_id: "tariff-2",
      billing_day: 5,
      status: "ACTIVE",
    });

    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(init.method).toBe("PATCH");
    expect(init.body).toBe(JSON.stringify({ status: "ACTIVE", billing_day: 5 }));
  });
});
