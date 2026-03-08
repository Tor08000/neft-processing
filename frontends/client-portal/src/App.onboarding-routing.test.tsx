import { describe, expect, it } from "vitest";
import { resolveLogicalRoute } from "./App";

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
});
