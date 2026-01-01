import type { CasePriority } from "../api/cases";

export type ExplainMode = "explain" | "diff" | "actions" | "case";

export interface ExplainQueryState {
  mode: ExplainMode;
  includeExplain: boolean;
  includeDiff: boolean;
  includeActions: boolean;
  selectedActions: string[];
  casePriority: CasePriority;
  caseNote: string;
  leftSnapshot: string;
  rightSnapshot: string;
  actionId: string;
}

export const DEFAULT_EXPLAIN_QUERY_STATE: ExplainQueryState = {
  mode: "explain",
  includeExplain: true,
  includeDiff: true,
  includeActions: true,
  selectedActions: [],
  casePriority: "MEDIUM",
  caseNote: "",
  leftSnapshot: "",
  rightSnapshot: "",
  actionId: "",
};

const parseBoolean = (value: string | null, fallback: boolean) => {
  if (value === "1" || value === "true") return true;
  if (value === "0" || value === "false") return false;
  return fallback;
};

const isMode = (value: string | null): value is ExplainMode =>
  value === "explain" || value === "diff" || value === "actions" || value === "case";

const isCasePriority = (value: string | null): value is CasePriority =>
  value === "LOW" || value === "MEDIUM" || value === "HIGH" || value === "CRITICAL";

const parseList = (value: string | null): string[] =>
  value ? value.split(",").map((item) => item.trim()).filter(Boolean) : [];

export const parseExplainQueryState = (params: URLSearchParams): ExplainQueryState => {
  const mode = isMode(params.get("mode")) ? params.get("mode") : DEFAULT_EXPLAIN_QUERY_STATE.mode;
  const includeExplain = parseBoolean(params.get("include_explain"), DEFAULT_EXPLAIN_QUERY_STATE.includeExplain);
  const includeDiff = parseBoolean(params.get("include_diff"), DEFAULT_EXPLAIN_QUERY_STATE.includeDiff);
  const includeActions = parseBoolean(params.get("include_actions"), DEFAULT_EXPLAIN_QUERY_STATE.includeActions);
  const selectedActions = parseList(params.get("selected_actions"));
  const casePriority = isCasePriority(params.get("case_priority"))
    ? params.get("case_priority")
    : DEFAULT_EXPLAIN_QUERY_STATE.casePriority;
  const caseNote = params.get("case_note") ?? DEFAULT_EXPLAIN_QUERY_STATE.caseNote;
  const leftSnapshot = params.get("left_snapshot") ?? DEFAULT_EXPLAIN_QUERY_STATE.leftSnapshot;
  const rightSnapshot = params.get("right_snapshot") ?? DEFAULT_EXPLAIN_QUERY_STATE.rightSnapshot;
  const actionId = params.get("action_id") ?? DEFAULT_EXPLAIN_QUERY_STATE.actionId;

  return {
    mode,
    includeExplain,
    includeDiff,
    includeActions,
    selectedActions,
    casePriority,
    caseNote,
    leftSnapshot,
    rightSnapshot,
    actionId,
  };
};

export const serializeExplainQueryState = (
  state: ExplainQueryState,
  baseParams: URLSearchParams,
): URLSearchParams => {
  const params = new URLSearchParams(baseParams.toString());
  params.set("mode", state.mode);
  params.set("include_explain", state.includeExplain ? "1" : "0");
  params.set("include_diff", state.includeDiff ? "1" : "0");
  params.set("include_actions", state.includeActions ? "1" : "0");
  if (state.selectedActions.length) {
    params.set("selected_actions", state.selectedActions.join(","));
  } else {
    params.delete("selected_actions");
  }
  params.set("case_priority", state.casePriority);
  if (state.caseNote) {
    params.set("case_note", state.caseNote);
  } else {
    params.delete("case_note");
  }
  if (state.leftSnapshot) {
    params.set("left_snapshot", state.leftSnapshot);
  } else {
    params.delete("left_snapshot");
  }
  if (state.rightSnapshot) {
    params.set("right_snapshot", state.rightSnapshot);
  } else {
    params.delete("right_snapshot");
  }
  if (state.actionId) {
    params.set("action_id", state.actionId);
  } else {
    params.delete("action_id");
  }
  return params;
};
