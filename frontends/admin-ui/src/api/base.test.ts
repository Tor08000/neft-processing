import { describe, expect, it } from "vitest";
import { joinUrl } from "./base";

describe("joinUrl", () => {
  it("joins auth under api base without duplication", () => {
    expect(joinUrl("http://localhost/api", "/auth/v1/auth/login")).toBe(
      "http://localhost/api/auth/v1/auth/login",
    );
  });

  it("preserves existing auth base", () => {
    expect(joinUrl("http://localhost/api/auth", "/v1/auth/login")).toBe(
      "http://localhost/api/auth/v1/auth/login",
    );
  });

  it("joins relative auth base", () => {
    expect(joinUrl("/api/auth", "/v1/auth/login")).toBe("/api/auth/v1/auth/login");
  });

  it("avoids duplicate api or auth segments", () => {
    expect(joinUrl("/api", "/api/auth/v1/auth/login")).toBe("/api/auth/v1/auth/login");
    expect(joinUrl("/api/auth", "/auth/v1/auth/login")).toBe("/api/auth/v1/auth/login");
  });
});
