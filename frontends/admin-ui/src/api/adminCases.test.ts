import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fetchAdminCases, listCaseEvents, NotAvailableError } from "./adminCases";

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

  it("normalizes legacy OPEN status to TRIAGE", async () => {
    const fetchMock = global.fetch as ReturnType<typeof vi.fn>;
    fetchMock.mockResolvedValue(
      buildResponse({
        items: [
          {
            id: "case-1",
            status: "OPEN",
            priority: "HIGH",
            title: "Legacy admin case",
            created_at: "2026-01-01T10:00:00Z",
          },
        ],
        total: 1,
        limit: 10,
      }),
    );

    const response = await fetchAdminCases({ limit: 10 });
    expect(response.items[0]?.status).toBe("TRIAGE");
    expect(fetchMock).toHaveBeenCalled();
  });

  it("throws NotAvailableError for 404", async () => {
    const fetchMock = global.fetch as ReturnType<typeof vi.fn>;
    fetchMock.mockResolvedValue(buildResponse({ detail: "Not found" }, { status: 404 }));

    await expect(fetchAdminCases({ limit: 10 })).rejects.toBeInstanceOf(NotAvailableError);
  });

  it("lists case events", async () => {
    const fetchMock = global.fetch as ReturnType<typeof vi.fn>;
    fetchMock.mockResolvedValue(
      buildResponse({
        items: [
          {
            id: "evt-1",
            at: "2026-01-01T10:00:00Z",
            type: "CASE_CREATED",
            actor: { email: "ops@neft.io" },
          },
        ],
      }),
    );

    const response = await listCaseEvents("case-1");
    expect(response.items).toHaveLength(1);
    expect(response.items[0].type).toBe("CASE_CREATED");
  });

  it("returns unavailable for 404 events endpoint", async () => {
    const fetchMock = global.fetch as ReturnType<typeof vi.fn>;
    fetchMock.mockResolvedValue(buildResponse({ detail: "Not found" }, { status: 404 }));

    const response = await listCaseEvents("case-1");
    expect(response.unavailable).toBe(true);
    expect(response.items).toEqual([]);
  });
});
