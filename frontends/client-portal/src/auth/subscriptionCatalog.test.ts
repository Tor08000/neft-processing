import { describe, expect, it } from "vitest";
import { SUBSCRIPTION_CATALOG, getPlansByAudience } from "@shared/subscriptions/catalog";

describe("subscription catalog", () => {
  it("has required client and partner plan counts", () => {
    const clientPlans = getPlansByAudience("CLIENT");
    const partnerPlans = getPlansByAudience("PARTNER");
    expect(clientPlans.filter((p) => p.isTrial).length).toBe(1);
    expect(clientPlans.filter((p) => !p.isTrial).length).toBe(5);
    expect(partnerPlans.length).toBe(5);
  });

  it("all plans have required fields and valid audience", () => {
    SUBSCRIPTION_CATALOG.forEach((plan) => {
      expect(["CLIENT", "PARTNER"]).toContain(plan.audience);
      expect(plan.code).toBeTruthy();
      expect(plan.title).toBeTruthy();
      expect(plan.description).toBeTruthy();
      expect(plan.bullets.length).toBeGreaterThan(0);
      expect(plan.modules.dashboard).toBeTypeOf("boolean");
    });
  });
});
