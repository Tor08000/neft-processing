import { describe, expect, it } from "vitest";
import { resolveClientSubscriptionTier, resolveClientWorkspace } from "./clientWorkspace";

describe("client workspace", () => {
  it("treats individual org type as individual workspace without business finance access", () => {
    const workspace = resolveClientWorkspace({
      client: {
        org: { id: "org-1", org_type: "INDIVIDUAL" },
        subscription: { plan_code: "CLIENT_START" },
        org_roles: [],
        user_roles: [],
        capabilities: [],
        nav_sections: [],
      } as never,
    });

    expect(workspace.clientKind).toBe("INDIVIDUAL");
    expect(workspace.hasFinanceWorkspace).toBe(false);
  });

  it("does not broaden workspace kind without portal-me business ownership", () => {
    const workspace = resolveClientWorkspace({
      client: {
        org: { id: "org-1", org_type: "INDIVIDUAL" },
        subscription: { plan_code: "CLIENT_BUSINESS" },
        modules: { fleet: { enabled: true }, analytics: { enabled: true } },
        org_roles: ["CLIENT_OWNER"],
        user_roles: ["CLIENT_OWNER"],
        capabilities: ["CLIENT_CORE"],
        nav_sections: [],
      } as never,
    });

    expect(workspace.clientKind).toBe("INDIVIDUAL");
    expect(workspace.hasFleetWorkspace).toBe(false);
    expect(workspace.hasFinanceWorkspace).toBe(false);
  });

  it("treats legal org type as business workspace", () => {
    const workspace = resolveClientWorkspace({
      client: {
        org: { id: "org-1", org_type: "LEGAL" },
        subscription: { plan_code: "CLIENT_BUSINESS" },
        modules: { fleet: { enabled: true }, analytics: { enabled: true } },
        org_roles: ["CLIENT_OWNER"],
        user_roles: ["CLIENT_OWNER"],
        capabilities: ["CLIENT_CORE"],
        nav_sections: [],
      } as never,
    });

    expect(workspace.clientKind).toBe("BUSINESS");
    expect(workspace.hasFinanceWorkspace).toBe(true);
    expect(workspace.hasFleetWorkspace).toBe(true);
    expect(workspace.hasAnalyticsWorkspace).toBe(true);
    expect(workspace.hasTeamWorkspace).toBe(true);
  });

  it("maps subscription tiers without inventing extra product levels", () => {
    expect(resolveClientSubscriptionTier("CLIENT_FREE_TRIAL")).toBe("FREE");
    expect(resolveClientSubscriptionTier("CLIENT_START")).toBe("STANDARD");
    expect(resolveClientSubscriptionTier("CLIENT_PRO")).toBe("PRO");
    expect(resolveClientSubscriptionTier("CLIENT_ENTERPRISE")).toBe("ENTERPRISE");
  });
});
