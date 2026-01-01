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

export interface WhatIfEvaluateRequest {
  subject: {
    type: "INSIGHT" | "FUEL_TX" | "ORDER" | "INVOICE";
    id: string;
  };
  max_candidates?: number;
}

export interface WhatIfResponse {
  subject: { type: string; id: string };
  candidates: {
    rank: number;
    action: { code: string; title: string };
    projection: { probability_improved_pct: number; expected_effect_label: string; window_days: number };
    memory: { memory_penalty_pct: number; cooldown: boolean };
    risk: { outlook: string; notes: string[] };
    what_if_score: number;
    explain: string[];
  }[];
}

export type ExplainDiffRiskLabel = "IMPROVED" | "WORSENED" | "NO_CHANGE";

export interface ExplainDiffReason {
  code: string;
  title: string;
  weight?: number | null;
}

export interface ExplainDiffEvidence {
  id: string;
  label: string;
  type?: string | null;
  source?: string | null;
  confidence?: number | null;
}

export interface ExplainDiffSnapshot {
  risk_score?: number | null;
  decision?: ExplainDecision | null;
  reasons: ExplainDiffReason[];
  evidence: ExplainDiffEvidence[];
}

export interface ExplainDiffResponse {
  before: ExplainDiffSnapshot;
  after: ExplainDiffSnapshot;
  diff: {
    risk: { delta: number; label: ExplainDiffRiskLabel };
    reasons: {
      removed: string[];
      weakened: { code: string; delta: number }[];
      strengthened: { code: string; delta: number }[];
      added: string[];
    };
    evidence: { removed: string[]; added: string[] };
  };
  meta: {
    simulation: boolean;
    confidence?: number | null;
    memory_penalty?: "LOW" | "MEDIUM" | "HIGH" | null;
  };
}
