import { describe, expect, it } from "vitest";
import { joinUrl } from "./base";

describe("joinUrl", () => {
  it("joins base and path with a single slash", () => {
    expect(joinUrl("http://localhost", "/api/auth/v1/auth/login")).toBe(
      "http://localhost/api/auth/v1/auth/login",
    );
  });

  it("trims trailing slashes from base", () => {
    expect(joinUrl("http://localhost/", "api/auth/v1/auth/login")).toBe(
      "http://localhost/api/auth/v1/auth/login",
    );
  });

  it("supports relative base paths", () => {
    expect(joinUrl("/api", "/auth/v1/auth/login")).toBe("/api/auth/v1/auth/login");
  });
});
