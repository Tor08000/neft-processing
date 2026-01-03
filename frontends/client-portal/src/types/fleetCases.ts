export type FleetCaseStatus = "OPEN" | "IN_PROGRESS" | "CLOSED" | string;
export type FleetCaseSeverity = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL" | string;
export type FleetCaseSourceType = "LIMIT_BREACH" | "ANOMALY" | string;
export type FleetCasePolicyAction = "AUTO_BLOCK" | "AUTO_BLOCK_CARD" | "ESCALATE" | "ESCALATE_CASE" | string;

export interface FleetCaseSource {
  type?: FleetCaseSourceType | null;
  ref_id?: string | null;
}

export interface FleetCaseScope {
  card_alias?: string | null;
  card_id?: string | null;
  group_name?: string | null;
  group_id?: string | null;
}

export interface FleetCaseListItem {
  case_id: string;
  title: string;
  case_kind?: string | null;
  status?: FleetCaseStatus | null;
  severity?: FleetCaseSeverity | null;
  opened_at?: string | null;
  last_updated_at?: string | null;
  source?: FleetCaseSource | null;
  scope?: FleetCaseScope | null;
  scope_type?: string | null;
  scope_id?: string | null;
  assigned_to?: string | null;
  policy_action?: FleetCasePolicyAction | null;
}

export interface FleetCaseExplainDetails {
  trigger?: FleetCaseSourceType | null;
  rule_name?: string | null;
  observed?: string | number | null;
  threshold?: string | number | null;
  baseline?: string | number | null;
  occurred_at?: string | null;
  policy_name?: string | null;
  policy_action?: FleetCasePolicyAction | null;
  cooldown_seconds?: number | null;
  context?: string | null;
}

export interface FleetCaseTimelineEvent {
  id?: string | null;
  timestamp?: string | null;
  occurred_at?: string | null;
  description?: string | null;
  title?: string | null;
  link?: string | null;
}

export interface FleetCaseResolution {
  summary?: string | null;
  reason?: string | null;
  actions_taken?: string | null;
  closed_by?: string | null;
  closed_at?: string | null;
}

export interface FleetCaseDetails extends FleetCaseListItem {
  explain?: FleetCaseExplainDetails | null;
  timeline?: FleetCaseTimelineEvent[] | null;
  comments?: string[] | null;
  notes?: string[] | null;
  audit_event_id?: string | null;
  decision_memory_id?: string | null;
  resolution?: FleetCaseResolution | null;
}

export interface FleetCaseListResponse {
  items: FleetCaseListItem[];
  unavailable?: boolean;
}

export interface FleetCaseDetailsResponse {
  item?: FleetCaseDetails;
  unavailable?: boolean;
}
