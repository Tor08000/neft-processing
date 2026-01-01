import { describe, expect, it } from "vitest";
import { getPayoutStateVariant } from "./PayoutStateBadge";

describe("PayoutStateBadge", () => {
  it("maps payout states to variants", () => {
    expect(getPayoutStateVariant("READY")).toBe("warning");
    expect(getPayoutStateVariant("SENT")).toBe("warning");
    expect(getPayoutStateVariant("SETTLED")).toBe("success");
    expect(getPayoutStateVariant("FAILED")).toBe("error");
    expect(getPayoutStateVariant("DRAFT")).toBe("neutral");
  });
});
