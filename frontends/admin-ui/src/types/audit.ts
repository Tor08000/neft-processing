export interface AuditEvent {
  id?: string;
  ts?: string;
  type?: string;
  action?: string;
  title?: string;
  actor?: string;
  reason?: string;
  correlation_id?: string;
  meta?: Record<string, unknown> | null;
  payload?: Record<string, unknown> | null;
}

export interface AuditFeedResponse {
  items: AuditEvent[];
  total?: number;
  limit?: number;
  offset?: number;
}

export interface AuditCorrelationResponse {
  correlation_id: string;
  items?: AuditEvent[];
  events?: AuditEvent[];
  chain?: string[];
}
