import { describe, expect, it } from "vitest";
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
    expect(joinUrl("/api", "/api/v1/auth/login")).toBe("/api/v1/auth/login");
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
    expect(joinUrl("http://localhost/api/v1/auth", "/login")).toBe(
      "http://localhost/api/v1/auth/login",
    );
    expect(joinUrl("http://localhost/api/api", "/auth/v1/auth/login")).toBe(
      "http://localhost/api/v1/auth/login",
    );
  });

  it("handles required joinUrl cases without duplicating segments", () => {
    expect(joinUrl("http://localhost", "/api/v1/auth/login")).toBe(
      "http://localhost/api/v1/auth/login",
    );
    expect(joinUrl("/api", "/auth/v1/auth/login")).toBe("/api/v1/auth/login");
    expect(joinUrl("/api", "/core/health")).toBe("/api/core/health");
    expect(joinUrl("/api/core", "/client/fleet/groups")).toBe("/api/core/client/fleet/groups");
    expect(joinUrl("/api/v1/auth", "/login")).toBe("/api/v1/auth/login");
    expect(joinUrl("http://localhost/api", "/auth/v1/auth/login")).toBe(
      "http://localhost/api/v1/auth/login",
    );
  });
});
