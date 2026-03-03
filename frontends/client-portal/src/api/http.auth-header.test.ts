import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { request } from "./http";

describe("http auth header attachment", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("skips bearer for invalid token and logs invalid_format", async () => {
    const infoSpy = vi.spyOn(console, "info").mockImplementation(() => undefined);
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200, headers: { "content-type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    await request("/portal/me", { method: "GET" }, { token: "not-a-jwt", base: "core" });

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const headers = init.headers as Record<string, string>;
    expect(headers.Authorization).toBeUndefined();
    expect(infoSpy).toHaveBeenCalledWith("[auth] skip_bearer reason=invalid_format");
  });
});
