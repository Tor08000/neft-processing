import { afterEach, describe, expect, it, vi } from "vitest";
import { joinUrl } from "./base";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.resetModules();
});

describe("joinUrl", () => {
  it("joins base and path with a single slash", () => {
    expect(joinUrl("http://localhost", "/api/v1/auth/login")).toBe(
      "http://localhost/api/v1/auth/login",
    );
  });

  it("trims trailing slashes from base", () => {
    expect(joinUrl("http://localhost/", "api/v1/auth/login")).toBe(
      "http://localhost/api/v1/auth/login",
    );
  });

  it("supports relative base paths", () => {
    expect(joinUrl("/api", "/auth/v1/auth/login")).toBe("/api/v1/auth/login");
  });

  it("avoids duplicating api segments", () => {
    expect(joinUrl("/api", "/api/auth/login")).toBe("/api/v1/auth/login");
    expect(joinUrl("http://localhost/api", "api/v1/auth/login")).toBe(
      "http://localhost/api/v1/auth/login",
    );
  });

  it("normalizes auth base segments", () => {
    expect(joinUrl("http://localhost/api", "/auth/v1/auth/login")).toBe(
      "http://localhost/api/v1/auth/login",
    );
    expect(joinUrl("http://localhost/api/auth", "/login")).toBe(
      "http://localhost/api/v1/auth/login",
    );
  });
});

describe("browser API base resolution", () => {
  it("Case A: normalizes gateway absolute URL to same-origin auth/core paths", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "http://gateway/api");
    vi.stubEnv("VITE_AUTH_API_BASE", "");
    vi.stubEnv("VITE_CORE_API_BASE", "");

    const baseModule = await import("./base");

    expect(baseModule.AUTH_API_BASE).toBe("/api/v1/auth");
    expect(baseModule.CORE_API_BASE).toBe("/api/core");
  });

  it("Case B: normalizes auth-host absolute URL to same-origin auth/core paths", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "http://auth-host:8000/api");
    vi.stubEnv("VITE_AUTH_API_BASE", "");
    vi.stubEnv("VITE_CORE_API_BASE", "");

    const baseModule = await import("./base");

    expect(baseModule.AUTH_API_BASE).toBe("/api/v1/auth");
    expect(baseModule.CORE_API_BASE).toBe("/api/core");
  });

  it("normalizes core-api absolute URL to same-origin auth/core paths", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "http://core-api:8000/api");
    vi.stubEnv("VITE_AUTH_API_BASE", "");
    vi.stubEnv("VITE_CORE_API_BASE", "");

    const baseModule = await import("./base");

    expect(baseModule.AUTH_API_BASE).toBe("/api/v1/auth");
    expect(baseModule.CORE_API_BASE).toBe("/api/core");
  });

  it("normalizes localhost container port URL to same-origin auth/core paths", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "http://localhost:8001/api");
    vi.stubEnv("VITE_AUTH_API_BASE", "");
    vi.stubEnv("VITE_CORE_API_BASE", "");

    const baseModule = await import("./base");

    expect(baseModule.AUTH_API_BASE).toBe("/api/v1/auth");
    expect(baseModule.CORE_API_BASE).toBe("/api/core");
  });

  it("Case C: keeps /api as same-origin auth/core paths", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "/api");
    vi.stubEnv("VITE_AUTH_API_BASE", "");
    vi.stubEnv("VITE_CORE_API_BASE", "");

    const baseModule = await import("./base");

    expect(baseModule.AUTH_API_BASE).toBe("/api/v1/auth");
    expect(baseModule.CORE_API_BASE).toBe("/api/core");
  });

  it("normalizes http://localhost/api to same-origin auth/core paths", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "http://localhost/api");
    vi.stubEnv("VITE_AUTH_API_BASE", "");
    vi.stubEnv("VITE_CORE_API_BASE", "");

    const baseModule = await import("./base");

    expect(baseModule.AUTH_API_BASE).toBe("/api/v1/auth");
    expect(baseModule.CORE_API_BASE).toBe("/api/core");
  });

  it("Case D: falls back to /api defaults when env is missing", async () => {
    vi.unstubAllEnvs();

    const baseModule = await import("./base");

    expect(baseModule.AUTH_API_BASE).toBe("/api/v1/auth");
    expect(baseModule.CORE_API_BASE).toBe("/api/core");
    expect(baseModule.API_BASE_URL).toBe("/api");
  });

  it("Case E: normalized same-origin paths are considered valid and not misconfigured", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "http://gateway/api");

    const baseModule = await import("./base");

    expect(baseModule.isBrowserSafeApiBase(baseModule.AUTH_API_BASE)).toBe(true);
    expect(baseModule.isBrowserSafeApiBase(baseModule.CORE_API_BASE)).toBe(true);
    expect(baseModule.isBrowserSafeApiBase("http://gateway/api")).toBe(true);
  });
});
