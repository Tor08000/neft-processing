export type ExplainDecision = "APPROVE" | "DECLINE" | "REVIEW";
export type ExplainScoreBand = "low" | "medium" | "high" | "block" | "review";
export type ExplainEvidenceType = "metric" | "field" | "rule" | "document" | "event";

export interface ExplainReasonNode {
  id: string;
  title: string;
  weight: number;
  children?: ExplainReasonNode[];
  evidence_refs?: string[];
}

export interface ExplainEvidence {
  id: string;
  type: ExplainEvidenceType;
  label: string;
  value?: Record<string, unknown> | string | number | null;
  source?: string | null;
  confidence?: number | null;
}

export interface ExplainDocument {
  id: string;
  title: string;
  kind: string;
  url: string;
}

export interface ExplainRecommendedAction {
  action_code: string;
  title: string;
  description?: string | null;
  expected_effect?: string | null;
  priority?: "low" | "medium" | "high" | null;
}

export interface ExplainActionCatalogItem {
  action_code: string;
  label: string;
  description?: string | null;
  risk_hint?: string | null;
  side_effects?: string | null;
}

export interface ExplainV2Response {
  kind: "operation" | "invoice" | "marketplace_order" | "kpi";
  id: string;
  decision: ExplainDecision;
  score?: number | null;
  score_band?: ExplainScoreBand | null;
  policy_snapshot?: string | null;
  generated_at: string;
  reason_tree?: ExplainReasonNode | null;
  evidence: ExplainEvidence[];
  documents: ExplainDocument[];
  recommended_actions: ExplainRecommendedAction[];
}

export type ExplainDiffReasonStatus = "added" | "removed" | "strengthened" | "weakened" | "unchanged";
export type ExplainDiffEvidenceStatus = "added" | "removed" | "changed";

export interface ExplainDiffResponse {
  meta: {
    kind: "operation" | "invoice" | "order" | "kpi";
    entity_id?: string | null;
    left: { snapshot_id: string; label: string };
    right: { snapshot_id: string; label: string };
  };
  score_diff: { risk_before?: number | null; risk_after?: number | null; delta?: number | null };
  decision_diff: { before?: ExplainDecision | null; after?: ExplainDecision | null };
  reasons_diff: {
    reason_code: string;
    weight_before?: number | null;
    weight_after?: number | null;
    delta: number;
    status: ExplainDiffReasonStatus;
  }[];
  evidence_diff: { evidence_id: string; status: ExplainDiffEvidenceStatus }[];
  action_impact?: { action_id: string; expected_delta: number; confidence: number } | null;
}
