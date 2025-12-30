export interface ExplainActionItem {
  code: string;
  title: string;
  description: string;
  target?: string | null;
  severity: "INFO" | "REQUIRED";
}

export interface ExplainSla {
  started_at: string;
  expires_at: string;
  remaining_minutes: number;
}

export interface ExplainEscalation {
  target: string;
  status: "PENDING";
}

export interface UnifiedExplainResponse {
  primary_reason: string;
  secondary_reasons: string[];
  recommendations: string[];
  actions: ExplainActionItem[];
  sla?: ExplainSla | null;
  escalation?: ExplainEscalation | null;
  confidence?: number | null;
  timeline?: ExplainTimelineEvent[] | null;
}

export interface ExplainTimelineEvent {
  id: string;
  at: string;
  stage: "SIGNAL" | "RULE" | "DECISION";
  label: string;
  details?: string | null;
}

export interface ExplainInsightItem {
  reason: string;
  count: number;
}

export interface ExplainInsightsResponse {
  from: string;
  to: string;
  top_primary_reasons: ExplainInsightItem[];
  trend: Array<{ date: string; reason: string; count: number }>;
  top_decline_reasons: ExplainInsightItem[];
  top_decline_stations: ExplainInsightItem[];
}
