export type AuditPayload = {
  id: string;
  case_id: string;
  at: string;
  type: string;
  actor: { id?: string; email?: string } | null;
  request_id?: string | null;
  trace_id?: string | null;
  changes?: Array<{ field: string; from: unknown; to: unknown }>;
  artifact?: { kind: string; id: string; url?: string | null } | null;
  reason?: string | null;
  source: "backend" | "synthetic" | "local";
};

export type ChainLink = {
  event_id: string;
  prev_hash: string;
  hash: string;
};

export type ChainVerificationResult = {
  status: "verified" | "broken" | "unknown";
  broken_at_index?: number;
  expected_hash?: string;
  actual_hash?: string;
};
