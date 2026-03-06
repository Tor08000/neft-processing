import { describe, expect, it, vi } from "vitest";
import { joinUrl } from "./base";

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
    expect(joinUrl("http://localhost/api/", "auth/v1/auth/login")).toBe(
      "http://localhost/api/v1/auth/login",
    );
    expect(joinUrl("http://localhost/api/auth", "/login")).toBe(
      "http://localhost/api/v1/auth/login",
    );
    expect(joinUrl("http://localhost/api/api", "/auth/v1/auth/login")).toBe(
      "http://localhost/api/v1/auth/login",
    );
  });

  it("handles required joinUrl cases without duplicating segments", () => {
    expect(joinUrl("http://localhost", "/api/auth/login")).toBe(
      "http://localhost/api/v1/auth/login",
    );
    expect(joinUrl("/api", "/auth/v1/auth/login")).toBe("/api/v1/auth/login");
    expect(joinUrl("/api", "/core/health")).toBe("/api/core/health");
    expect(joinUrl("/api/core", "/client/fleet/groups")).toBe("/api/core/client/fleet/groups");
    expect(joinUrl("/api/auth", "/login")).toBe("/api/v1/auth/login");
    expect(joinUrl("http://localhost/api", "/auth/v1/auth/login")).toBe(
      "http://localhost/api/v1/auth/login",
    );
  });
});

describe("api base defaults", () => {
  it("keeps auth/core base same-origin when docker hostname is configured", async () => {
    vi.resetModules();
    vi.stubEnv("VITE_API_BASE_URL", "http://gateway/api");
    vi.stubEnv("VITE_AUTH_API_BASE", "");
    vi.stubEnv("VITE_CORE_API_BASE", "");

    const baseModule = await import("./base");

    expect(baseModule.AUTH_API_BASE).toBe("/api/v1/auth");
    expect(baseModule.CORE_API_BASE).toBe("/api/core");
  });
});
