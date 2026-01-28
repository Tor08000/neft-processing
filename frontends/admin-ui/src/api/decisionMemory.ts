import { apiGet } from "./client";

export type DecisionMemoryEntry = {
  id: string;
  case_id?: string | null;
  decision_type: "explain" | "diff" | "action" | "close";
  decision_ref_id: string;
  decision_at: string;
  decided_by_user_id?: string | null;
  context_snapshot?: Record<string, unknown>;
  rationale?: string | null;
  score_snapshot?: Record<string, unknown> | null;
  mastery_snapshot?: Record<string, unknown> | null;
  audit_event_id: string;
  created_at: string;
  audit_chain_verified: boolean;
  audit_signature_verified: boolean;
  artifact_signature_verified?: boolean | null;
};

export type DecisionMemoryListResponse = {
  items: DecisionMemoryEntry[];
  next_cursor?: string | null;
};

export const listDecisionMemory = async (caseId: string): Promise<DecisionMemoryListResponse> => {
  return apiGet(`/cases/${caseId}/decisions`);
};
