import { describe, expect, it } from "vitest";
import { resolveActiveClientMode, resolveAvailableClientModes } from "./clientModes";

describe("client modes", () => {
  it("returns personal-only mode for single-mode users", () => {
    expect(
      resolveAvailableClientModes({
        journeyState: "ACTIVE",
        draft: { selectedPlan: "CLIENT_START", customerType: "INDIVIDUAL" },
        client: { capabilities: [], access_state: "ACTIVE" } as never,
      }),
    ).toEqual(["personal"]);
  });

  it("returns personal and fleet for users with fleet-enabled plan", () => {
    expect(
      resolveAvailableClientModes({
        journeyState: "ACTIVE",
        draft: { selectedPlan: "CLIENT_SMART", customerType: "LEGAL_ENTITY" },
        client: { capabilities: [], access_state: "ACTIVE" } as never,
      }),
    ).toEqual(["personal", "fleet"]);
  });

  it("falls back to an allowed mode when current mode is unavailable", () => {
    expect(resolveActiveClientMode("fleet", ["personal"])).toBe("personal");
  });
});
