export type FleetAlertSeverity = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL" | string;
export type FleetAlertStatus = "OPEN" | "ACKED" | "IGNORED" | string;
export type FleetAlertType = "LIMIT_BREACH" | "ANOMALY" | "INGEST_FAILED" | string;

export interface FleetAlert {
  id: string;
  status?: FleetAlertStatus;
  severity?: FleetAlertSeverity;
  type?: FleetAlertType;
  summary?: string | null;
  occurred_at?: string | null;
  scope_type?: "CARD" | "GROUP" | "CLIENT" | string | null;
  card_id?: string | null;
  card_alias?: string | null;
  group_id?: string | null;
  group_name?: string | null;
  rule_name?: string | null;
  why?: string | null;
  observed_value?: number | string | null;
  baseline_value?: number | string | null;
  limit_value?: number | string | null;
  merchant?: string | null;
  category?: string | null;
}

export type FleetChannelType = "WEBHOOK" | "EMAIL" | "PUSH" | string;

export interface FleetNotificationChannel {
  id: string;
  channel_type?: FleetChannelType;
  target?: string | null;
  status?: "ACTIVE" | "DISABLED" | string | null;
  created_at?: string | null;
}

export interface FleetPushSubscription {
  id: string;
  endpoint: string;
  active: boolean;
  created_at?: string | null;
  last_sent_at?: string | null;
}

export interface FleetNotificationPolicy {
  id: string;
  scope_type?: "CLIENT" | "GROUP" | "CARD" | string | null;
  group_name?: string | null;
  card_alias?: string | null;
  event_type?: FleetAlertType | string | null;
  severity_min?: FleetAlertSeverity | null;
  channels?: FleetNotificationChannel[] | null;
  channel_ids?: string[] | null;
  channel_types?: FleetChannelType[] | null;
  cooldown_seconds?: number | null;
  auto_action?: "NONE" | "AUTO_BLOCK" | string | null;
  status?: "ACTIVE" | "DISABLED" | string | null;
}
