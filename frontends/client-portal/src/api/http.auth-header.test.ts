import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { request, requestWithMeta } from "./http";

describe("http auth header attachment", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.stubEnv("VITE_CLIENT_DEBUG_HTTP", "true");
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("skips bearer for invalid token and logs invalid_format", async () => {
    const infoSpy = vi.spyOn(console, "log").mockImplementation(() => undefined);
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200, headers: { "content-type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    await request("/portal/me", { method: "GET" }, { token: "not-a-jwt", base: "core" });

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const headers = init.headers as Record<string, string>;
    expect(headers.Authorization).toBeUndefined();
    expect(infoSpy).toHaveBeenCalledWith("[HTTP] skip_bearer reason=invalid_format");
  });
});


it("treats 200 with empty json body as success in requestWithMeta", async () => {
  const fetchMock = vi.fn().mockResolvedValue(new Response("", { status: 200, headers: { "content-type": "application/json" } }));
  vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

  const response = await requestWithMeta<Record<string, never>>("/client/onboarding/profile", { method: "POST" }, { token: "aaa.bbb.ccc", base: "core" });

  expect(response.status).toBe(200);
  expect(response.data).toEqual({});
});

it("treats 200 with empty json body as success in request", async () => {
  const fetchMock = vi.fn().mockResolvedValue(new Response("", { status: 200, headers: { "content-type": "application/json" } }));
  vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

  const response = await request<Record<string, never>>("/client/onboarding/profile", { method: "POST" }, { token: "aaa.bbb.ccc", base: "core" });

  expect(response).toEqual({});
});
