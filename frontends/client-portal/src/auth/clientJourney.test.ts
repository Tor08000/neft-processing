import { describe, expect, it } from "vitest";
import { resolveClientJourneyState } from "./clientJourney";

describe("resolveClientJourneyState", () => {
  it("returns demo showcase for demo users", () => {
    expect(resolveClientJourneyState({ authStatus: "authenticated", isDemo: true, client: null, draft: {} })).toBe("DEMO_SHOWCASE");
  });

  it("returns needs plan for authenticated unconnected", () => {
    expect(resolveClientJourneyState({ authStatus: "authenticated", isDemo: false, client: null, draft: {} })).toBe("NEEDS_PLAN");
  });

  it("moves through type/profile/doc/sign/payment", () => {
    expect(
      resolveClientJourneyState({
        authStatus: "authenticated",
        isDemo: false,
        client: null,
        draft: { selectedPlan: "START" },
      }),
    ).toBe("NEEDS_CUSTOMER_TYPE");

    expect(
      resolveClientJourneyState({
        authStatus: "authenticated",
        isDemo: false,
        client: null,
        draft: { selectedPlan: "START", customerType: "INDIVIDUAL" },
      }),
    ).toBe("NEEDS_PROFILE");

    expect(
      resolveClientJourneyState({
        authStatus: "authenticated",
        isDemo: false,
        client: null,
        draft: { selectedPlan: "START", customerType: "INDIVIDUAL", profileCompleted: true },
      }),
    ).toBe("NEEDS_DOCUMENTS");

    expect(
      resolveClientJourneyState({
        authStatus: "authenticated",
        isDemo: false,
        client: null,
        draft: {
          selectedPlan: "START",
          customerType: "INDIVIDUAL",
          profileCompleted: true,
          documentsGenerated: true,
          documentsViewed: true,
        },
      }),
    ).toBe("NEEDS_SIGNATURE");

    expect(
      resolveClientJourneyState({
        authStatus: "authenticated",
        isDemo: false,
        client: null,
        draft: {
          selectedPlan: "START",
          customerType: "INDIVIDUAL",
          profileCompleted: true,
          documentsGenerated: true,
          documentsViewed: true,
          documentsSigned: true,
          paymentStatus: "pending",
        },
      }),
    ).toBe("NEEDS_PAYMENT");
  });

  it("returns active when payment succeeds", () => {
    expect(
      resolveClientJourneyState({
        authStatus: "authenticated",
        isDemo: false,
        client: null,
        draft: { paymentStatus: "succeeded" },
      }),
    ).toBe("ACTIVE");
  });
});
