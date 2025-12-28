import { describe, expect, it } from "vitest";
import { getPayoutStateColor } from "./PayoutStateBadge";

describe("PayoutStateBadge", () => {
  it("maps payout states to colors", () => {
    expect(getPayoutStateColor("READY")).toBe("#64748b");
    expect(getPayoutStateColor("SENT")).toBe("#0ea5e9");
    expect(getPayoutStateColor("SETTLED")).toBe("#16a34a");
    expect(getPayoutStateColor("FAILED")).toBe("#dc2626");
    expect(getPayoutStateColor("DRAFT")).toBe("#94a3b8");
  });
});
