import { describe, expect, it } from "vitest";
import { resolveClientJourneyState } from "./clientJourney";

describe("resolveClientJourneyState", () => {
  it("returns demo showcase for demo users", () => {
    expect(resolveClientJourneyState({ authStatus: "authenticated", isDemo: true, client: null, draft: {} })).toBe("DEMO_SHOWCASE");
  });

  it("returns authenticated unconnected for a fresh real account", () => {
    expect(resolveClientJourneyState({ authStatus: "authenticated", isDemo: false, client: null, draft: {} })).toBe("AUTHENTICATED_UNCONNECTED");
  });

  it("moves through plan/type/profile/doc/sign/payment states", () => {
    expect(resolveClientJourneyState({ authStatus: "authenticated", isDemo: false, client: { access_state: "NEEDS_ONBOARDING" } as never, draft: {} })).toBe("AUTHENTICATED_UNCONNECTED");
    expect(resolveClientJourneyState({ authStatus: "authenticated", isDemo: false, client: null, draft: { selectedPlan: "CLIENT_START" } })).toBe("NEEDS_CUSTOMER_TYPE");
    expect(resolveClientJourneyState({ authStatus: "authenticated", isDemo: false, client: null, draft: { selectedPlan: "CLIENT_START", customerType: "INDIVIDUAL" } })).toBe("NEEDS_PROFILE");
    expect(resolveClientJourneyState({ authStatus: "authenticated", isDemo: false, client: null, draft: { selectedPlan: "CLIENT_START", customerType: "INDIVIDUAL", profileCompleted: true } })).toBe("NEEDS_DOCUMENTS");
    expect(resolveClientJourneyState({ authStatus: "authenticated", isDemo: false, client: null, draft: { selectedPlan: "CLIENT_START", customerType: "INDIVIDUAL", profileCompleted: true, documentsGenerated: true, documentsViewed: true } })).toBe("NEEDS_SIGNATURE");
    expect(resolveClientJourneyState({ authStatus: "authenticated", isDemo: false, client: null, draft: { selectedPlan: "CLIENT_START", customerType: "INDIVIDUAL", profileCompleted: true, documentsGenerated: true, documentsViewed: true, documentsSigned: true, subscriptionState: "PAYMENT_PENDING" } })).toBe("NEEDS_PAYMENT");
  });

  it("supports free trial activation", () => {
    expect(resolveClientJourneyState({ authStatus: "authenticated", isDemo: false, client: null, draft: { selectedPlan: "CLIENT_FREE_TRIAL", customerType: "INDIVIDUAL", profileCompleted: true, documentsGenerated: true, documentsViewed: true, documentsSigned: true } })).toBe("TRIAL_ACTIVE");
  });

  it("returns active when payment succeeds", () => {
    expect(resolveClientJourneyState({ authStatus: "authenticated", isDemo: false, client: null, draft: { subscriptionState: "ACTIVE" } })).toBe("ACTIVE");
  });
});
