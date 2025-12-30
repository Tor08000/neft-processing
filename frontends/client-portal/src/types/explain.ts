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
}
