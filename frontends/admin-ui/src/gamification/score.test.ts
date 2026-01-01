import { describe, expect, it } from "vitest";
import type { ExplainV2Response } from "../types/explainV2";
import { computeExplainScore } from "./score";

const baseExplain: ExplainV2Response = {
  kind: "operation",
  id: "op_1",
  decision: "APPROVE",
  score: 0.1,
  score_band: "low",
  policy_snapshot: null,
  generated_at: "2024-01-01T00:00:00Z",
  reason_tree: null,
  evidence: [],
  documents: [],
  recommended_actions: [],
};

describe("computeExplainScore", () => {
  it("returns critical for declined decisions", () => {
    const result = computeExplainScore({ ...baseExplain, decision: "DECLINE", score: 0.2 });
    expect(result.level).toBe("critical");
  });

  it("returns risky for medium score band", () => {
    const result = computeExplainScore({ ...baseExplain, score_band: "medium", score: 0.5 });
    expect(result.level).toBe("risky");
    expect(result.penalty).toBe(50);
  });

  it("averages confidence from evidence", () => {
    const result = computeExplainScore({
      ...baseExplain,
      evidence: [
        { id: "1", type: "rule", label: "r1", confidence: 0.6 },
        { id: "2", type: "metric", label: "r2", confidence: 0.8 },
      ],
    });
    expect(result.confidence).toBeCloseTo(0.7, 3);
  });
});
