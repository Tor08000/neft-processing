import { describe, expect, it } from "vitest";
import { DEFAULT_EXPLAIN_QUERY_STATE, parseExplainQueryState, serializeExplainQueryState } from "./explainQueryState";

describe("explainQueryState", () => {
  it("parses query params with strict booleans and lists", () => {
    const params = new URLSearchParams(
      "mode=diff&include_explain=0&include_diff=1&include_actions=false&selected_actions=a1,b2" +
        "&case_priority=HIGH&case_note=hello&left_snapshot=left&right_snapshot=right&action_id=act",
    );

    expect(parseExplainQueryState(params)).toEqual({
      mode: "diff",
      includeExplain: false,
      includeDiff: true,
      includeActions: false,
      selectedActions: ["a1", "b2"],
      casePriority: "HIGH",
      caseNote: "hello",
      leftSnapshot: "left",
      rightSnapshot: "right",
      actionId: "act",
    });
  });

  it("serializes query params while preserving base params", () => {
    const base = new URLSearchParams("kind=invoice&id=42");
    const params = serializeExplainQueryState(
      {
        ...DEFAULT_EXPLAIN_QUERY_STATE,
        mode: "actions",
        includeActions: false,
        selectedActions: ["a1"],
        caseNote: "note",
      },
      base,
    );

    expect(params.get("kind")).toBe("invoice");
    expect(params.get("id")).toBe("42");
    expect(params.get("mode")).toBe("actions");
    expect(params.get("include_actions")).toBe("0");
    expect(params.get("selected_actions")).toBe("a1");
    expect(params.get("case_note")).toBe("note");
  });
});
