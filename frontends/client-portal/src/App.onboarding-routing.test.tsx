import { describe, expect, it } from "vitest";
import { resolveLogicalRoute, resolveSafeClientReturnUrl } from "./App";

describe("onboarding route resolution", () => {
  it("marks onboarding aliases", () => {
    expect(resolveLogicalRoute("/client/onboarding")).toBe("onboarding_alias");
    expect(resolveLogicalRoute("/client/onboarding/plan")).toBe("onboarding_alias");
    expect(resolveLogicalRoute("/client/onboarding/contract")).toBe("onboarding_alias");
  });

  it("marks canonical onboarding and dashboard buckets", () => {
    expect(resolveLogicalRoute("/onboarding")).toBe("onboarding");
    expect(resolveLogicalRoute("/operations/123")).toBe("operations");
    expect(resolveLogicalRoute("/dashboard")).toBe("dashboard");
  });

  it("preserves safe deep-link return urls for authenticated login entry", () => {
    expect(resolveSafeClientReturnUrl("/marketplace/orders/order-1", "/dashboard")).toBe("/marketplace/orders/order-1");
    expect(resolveSafeClientReturnUrl("/cases/case-1", "/dashboard")).toBe("/cases/case-1");
  });

  it("falls back to the journey route for auth-entry or external return urls", () => {
    expect(resolveSafeClientReturnUrl(null, "/dashboard")).toBe("/dashboard");
    expect(resolveSafeClientReturnUrl("https://evil.example/path", "/dashboard")).toBe("/dashboard");
    expect(resolveSafeClientReturnUrl("//evil.example/path", "/dashboard")).toBe("/dashboard");
    expect(resolveSafeClientReturnUrl("/login?returnUrl=%2Fmarketplace%2Forders%2Forder-1", "/dashboard")).toBe("/dashboard");
  });
});
