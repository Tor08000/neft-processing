import { apiGet, apiPost } from "./client";

export type RuleSetVersion = {
  id: number;
  name: string;
  scope: string;
  status: string;
  created_at: string;
  published_at?: string | null;
  activated_at?: string | null;
  notes?: string | null;
};

export type SandboxRequest =
  | {
      mode: "synthetic";
      at: string;
      scope: string;
      context: Record<string, unknown>;
      synthetic_metrics: Record<string, number>;
      version_id?: number | null;
    }
  | {
      mode: "historical";
      scope: string;
      transaction_id: string;
      version_id?: number | null;
    };

export type SandboxMatchedRule = {
  code: string;
  policy: string;
  priority: number;
  reason_code?: string | null;
  explain?: string | null;
};

export type SandboxResponse = {
  version?: { rule_set_version_id: number; scope: string } | null;
  matched_rules: SandboxMatchedRule[];
  decision: string;
  reason_codes: string[];
  explain: {
    inputs: Record<string, unknown>;
    metrics: Record<string, unknown>;
    resolution: Record<string, unknown>;
  };
};

export async function fetchRuleSetVersions(scope?: string): Promise<RuleSetVersion[]> {
  return apiGet("/api/core/v1/admin/rules/versions", scope ? { scope } : undefined);
}

export async function evaluateRulesSandbox(payload: SandboxRequest): Promise<SandboxResponse> {
  return apiPost("/api/core/rules/sandbox:evaluate", payload);
}
