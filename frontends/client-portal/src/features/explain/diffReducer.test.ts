import { describe, expect, it } from "vitest";
import { reduceExplainDiffReasons } from "./diffReducer";

describe("reduceExplainDiffReasons", () => {
  it("filters reasons by tab", () => {
    const reasons = [
      { reason_code: "velocity_high", delta: -0.2, status: "weakened" as const },
      { reason_code: "trusted_device", delta: 0.1, status: "strengthened" as const },
      { reason_code: "new_signal", delta: 0.2, status: "added" as const },
    ];

    const strong = reduceExplainDiffReasons(reasons, "strong");
    expect(strong.visible).toHaveLength(2);

    const added = reduceExplainDiffReasons(reasons, "added");
    expect(added.visible).toHaveLength(1);

    const all = reduceExplainDiffReasons(reasons, "all");
    expect(all.visible).toHaveLength(3);
  });
});
