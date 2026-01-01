import type { ExplainDiffResponse } from "../../types/explainV2";

export type ExplainDiffTab = "strong" | "added" | "removed" | "all";

export interface ExplainDiffReasonView {
  reason_code: string;
  weight_before?: number | null;
  weight_after?: number | null;
  delta: number;
  status: ExplainDiffResponse["reasons_diff"][number]["status"];
}

const matchesTab = (reason: ExplainDiffReasonView, tab: ExplainDiffTab) => {
  if (tab === "all") return true;
  if (tab === "strong") return reason.status === "strengthened" || reason.status === "weakened";
  if (tab === "added") return reason.status === "added";
  return reason.status === "removed";
};

export const reduceExplainDiffReasons = (
  reasons: ExplainDiffReasonView[],
  tab: ExplainDiffTab,
): { visible: ExplainDiffReasonView[]; hiddenCount: number } => {
  const visible = reasons.filter((reason) => matchesTab(reason, tab));
  return { visible, hiddenCount: reasons.length - visible.length };
};
