import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fetchAdminCases, NotAvailableError } from "./adminCases";

const buildResponse = (payload: unknown, init: ResponseInit = {}) =>
  new Response(JSON.stringify(payload), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init,
  });

describe("admin cases api", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    global.fetch = originalFetch;
  });

  it("fetches cases list", async () => {
    const fetchMock = global.fetch as ReturnType<typeof vi.fn>;
    fetchMock.mockResolvedValue(buildResponse({ items: [], total: 0, limit: 10 }));

    const response = await fetchAdminCases({ limit: 10 });
    expect(response.items).toEqual([]);
    expect(fetchMock).toHaveBeenCalled();
  });

  it("throws NotAvailableError for 404", async () => {
    const fetchMock = global.fetch as ReturnType<typeof vi.fn>;
    fetchMock.mockResolvedValue(buildResponse({ detail: "Not found" }, { status: 404 }));

    await expect(fetchAdminCases({ limit: 10 })).rejects.toBeInstanceOf(NotAvailableError);
  });
});
