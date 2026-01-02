export type FleetPolicyScopeType = "CLIENT" | "GROUP" | "CARD" | string;
export type FleetPolicyTriggerType = "LIMIT_BREACH" | "ANOMALY" | string;
export type FleetPolicySeverity = "LOW" | "MED" | "HIGH" | "CRIT" | string;
export type FleetPolicyBreachKind = "HARD" | "SOFT" | "ANY" | string;
export type FleetPolicyAction = "NOTIFY_ONLY" | "AUTO_BLOCK_CARD" | "ESCALATE_CASE" | string;
export type FleetPolicyStatus = "ACTIVE" | "DISABLED" | string;
export type FleetPolicyExecutionStatus = "APPLIED" | "SKIPPED" | "FAILED" | string;

export interface FleetPolicy {
  id: string;
  scope_type: FleetPolicyScopeType;
  scope_id?: string | null;
  scope_label?: string | null;
  group_name?: string | null;
  card_alias?: string | null;
  trigger_type?: FleetPolicyTriggerType | null;
  severity_min?: FleetPolicySeverity | null;
  breach_kind?: FleetPolicyBreachKind | null;
  action?: FleetPolicyAction | null;
  cooldown_seconds?: number | null;
  status?: FleetPolicyStatus | null;
  created_at?: string | null;
}

export interface FleetPolicyExecution {
  executed_at?: string | null;
  policy_id?: string | null;
  scope_type?: FleetPolicyScopeType | null;
  scope_id?: string | null;
  trigger_type?: FleetPolicyTriggerType | null;
  severity?: FleetPolicySeverity | null;
  action?: FleetPolicyAction | null;
  status?: FleetPolicyExecutionStatus | null;
  reason?: string | null;
  group_name?: string | null;
  card_alias?: string | null;
  breach_id?: string | null;
  anomaly_id?: string | null;
  case_id?: string | null;
  audit_event_id?: string | null;
}

export interface FleetPolicyExecutionFilters {
  from?: string;
  to?: string;
  status?: string;
  action?: string;
  scope_type?: string;
  scope_id?: string;
  trigger_type?: string;
  severity_min?: string;
}
