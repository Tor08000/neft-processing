import { afterEach, describe, expect, it, vi } from "vitest";
import { createSupportRequest, fetchSupportRequest, fetchSupportRequests } from "./support";

describe("partner support api", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("calls create support request via canonical cases path", async () => {
    const fetchMock = vi.fn(async () =>
      new Response(
        JSON.stringify({
          id: "support-1",
          tenant_id: 1,
          kind: "order",
          entity_type: "ORDER",
          entity_id: "order-1",
          partner_id: "partner-1",
          title: "Need help",
          description: "Order issue",
          status: "TRIAGE",
          priority: "MEDIUM",
          created_at: "2026-04-01T00:00:00Z",
          updated_at: "2026-04-01T00:00:00Z",
        }),
        {
          status: 201,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    await createSupportRequest(
      {
        scope_type: "PARTNER",
        subject_type: "ORDER",
        subject_id: "order-1",
        title: "Need help",
        description: "Order issue",
      },
      "token-1",
    );

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, request] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/api/core/cases");
    expect(url).not.toContain("/api/v1/support/requests");
    expect(request.method).toBe("POST");
  });

  it("calls support requests list via canonical cases path with filters", async () => {
    const fetchMock = vi.fn(async () =>
      new Response(JSON.stringify({ items: [], total: 0, limit: 100, next_cursor: null }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    await fetchSupportRequests("token-1", {
      status: "OPEN",
      subject_type: "ORDER",
      from: "2026-04-01",
      to: "2026-04-02",
      limit: 25,
      offset: 10,
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url] = fetchMock.mock.calls[0] as [string, RequestInit];
    const parsed = new URL(url, "http://test.local");
    expect(url).toContain("/api/core/cases");
    expect(url).not.toContain("/api/v1/support/requests");
    expect(parsed.pathname).toBe("/api/core/cases");
    expect(parsed.searchParams.get("status")).toBe("TRIAGE");
    expect(parsed.searchParams.get("entity_type")).toBe("ORDER");
    expect(parsed.searchParams.get("limit")).toBe("100");
  });

  it("calls support request detail via canonical cases path", async () => {
    const fetchMock = vi.fn(async () =>
      new Response(
        JSON.stringify({
          case: {
            id: "support-42",
            tenant_id: 1,
            kind: "order",
            entity_type: "ORDER",
            entity_id: "order-1",
            partner_id: "partner-1",
            title: "Need help",
            description: "Order issue",
            status: "TRIAGE",
            priority: "MEDIUM",
            created_at: "2026-04-01T00:00:00Z",
            updated_at: "2026-04-01T00:00:00Z",
          },
          comments: [],
          timeline: [{ status: "TRIAGE", occurred_at: "2026-04-01T00:00:00Z" }],
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    await fetchSupportRequest("support-42", "token-1");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/api/core/cases/support-42");
    expect(url).not.toContain("/api/v1/support/requests/support-42");
  });
});
