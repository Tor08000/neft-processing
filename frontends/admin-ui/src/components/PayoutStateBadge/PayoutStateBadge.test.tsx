import { describe, expect, it } from "vitest";
import { getPayoutStateVariant } from "./PayoutStateBadge";

describe("PayoutStateBadge", () => {
  it("maps payout states to variants", () => {
    expect(getPayoutStateVariant("READY")).toBe("warn");
    expect(getPayoutStateVariant("SENT")).toBe("warn");
    expect(getPayoutStateVariant("SETTLED")).toBe("ok");
    expect(getPayoutStateVariant("FAILED")).toBe("err");
    expect(getPayoutStateVariant("DRAFT")).toBe("muted");
  });
});
