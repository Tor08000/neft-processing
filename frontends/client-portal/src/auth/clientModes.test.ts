import { describe, expect, it } from "vitest";
import { resolveActiveClientMode, resolveAvailableClientModes } from "./clientModes";

describe("client modes", () => {
  it("returns personal-only mode for single-mode users", () => {
    expect(
      resolveAvailableClientModes({
        journeyState: "ACTIVE",
        client: { capabilities: [], access_state: "ACTIVE" } as never,
      }),
    ).toEqual(["personal"]);
  });

  it("returns personal and fleet for business users with fleet-enabled runtime signals", () => {
    expect(
      resolveAvailableClientModes({
        journeyState: "ACTIVE",
        client: {
          org: { org_type: "LEGAL" },
          subscription: { plan_code: "CLIENT_SMART" },
          capabilities: [],
          access_state: "ACTIVE",
        } as never,
      }),
    ).toEqual(["personal", "fleet"]);
  });

  it("does not unlock fleet mode from stale onboarding draft alone", () => {
    expect(
      resolveAvailableClientModes({
        journeyState: "ACTIVE",
        client: {
          org: { org_type: "INDIVIDUAL" },
          access_state: "ACTIVE",
          capabilities: [],
          nav_sections: [],
        } as never,
      }),
    ).toEqual(["personal"]);
  });

  it("falls back to an allowed mode when current mode is unavailable", () => {
    expect(resolveActiveClientMode("fleet", ["personal"])).toBe("personal");
  });
});
