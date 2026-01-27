import { describe, expect, it, beforeEach, afterEach, vi } from "vitest";
import { QueryClient } from "@tanstack/react-query";
import { login } from "./auth";
import { fetchOperations } from "./operations";
import { TOKEN_STORAGE_KEY } from "./client";

function buildResponse(payload: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init,
  });
}

describe("api client caching and auth", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    localStorage.clear();
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    global.fetch = originalFetch;
  });

  it("re-fetches operations with refreshed token after login", async () => {
    const fetchMock = global.fetch as ReturnType<typeof vi.fn>;

    fetchMock.mockImplementation((url, init) => {
      const target = typeof url === "string" ? url : String(url);
      if (target.includes("/api/v1/auth/login")) {
        return Promise.resolve(
          buildResponse({ access_token: "new-token", expires_in: 3600, email: "demo@example.com", roles: [] }),
        );
      }

      const headers = (init?.headers ?? {}) as Record<string, string>;
      const authHeader = headers.Authorization;
      const body = { items: [], total: 0, receivedAuth: authHeader };
      return Promise.resolve(buildResponse(body));
    });

    localStorage.setItem(TOKEN_STORAGE_KEY, JSON.stringify({ accessToken: "initial-token" }));

    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });

    await queryClient.fetchQuery({
      queryKey: ["operations", { limit: 10, offset: 0 }],
      queryFn: () => fetchOperations({ limit: 10, offset: 0 }),
    });

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/core/v1/admin/operations"),
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: "Bearer initial-token" }),
      }),
    );

    const token = await login("demo@example.com", "secret");
    localStorage.setItem(TOKEN_STORAGE_KEY, JSON.stringify({ accessToken: token.accessToken }));
    await queryClient.invalidateQueries({ queryKey: ["operations"] });

    await queryClient.fetchQuery({
      queryKey: ["operations", { limit: 10, offset: 0 }],
      queryFn: () => fetchOperations({ limit: 10, offset: 0 }),
    });

    expect(fetchMock).toHaveBeenLastCalledWith(
      expect.stringContaining("/api/core/v1/admin/operations"),
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: "Bearer new-token" }),
      }),
    );
  });
});
