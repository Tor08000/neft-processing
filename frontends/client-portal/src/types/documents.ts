export interface ClientDocumentSummary {
  id: string;
  document_type: string;
  status: string;
  period_from: string;
  period_to: string;
  version: number;
  number?: string | null;
  created_at: string;
  pdf_hash?: string | null;
  risk?: ClientDocumentRiskSummary | null;
}

export interface ClientDocumentList {
  items: ClientDocumentSummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface ClientDocumentFile {
  file_type: string;
  sha256: string;
  size_bytes: number;
  content_type: string;
  created_at: string;
}

export interface ClientDocumentEvent {
  id: string;
  ts: string;
  event_type: string;
  action?: string | null;
  actor_type?: string | null;
  actor_id?: string | null;
  hash?: string | null;
  prev_hash?: string | null;
}

export interface ClientDocumentRiskSummary {
  state: string;
  decided_at?: string | null;
  decision_id?: string | null;
}

export interface ClientDocumentRiskExplain {
  decision_hash?: string | null;
  thresholds?: Record<string, number> | null;
  factors?: string[] | null;
  policy?: string | null;
  policy_id?: string | null;
}

export interface ClientDocumentAckDetails {
  ack_by_user_id?: string | null;
  ack_by_email?: string | null;
  ack_ip?: string | null;
  ack_user_agent?: string | null;
  ack_method?: string | null;
  ack_at?: string | null;
}

export interface ClientDocumentDetails {
  id: string;
  document_type: string;
  status: string;
  period_from: string;
  period_to: string;
  version: number;
  number?: string | null;
  created_at: string;
  generated_at?: string | null;
  sent_at?: string | null;
  ack_at?: string | null;
  document_hash?: string | null;
  files: ClientDocumentFile[];
  events: ClientDocumentEvent[];
  ack_details?: ClientDocumentAckDetails | null;
  risk?: ClientDocumentRiskSummary | null;
  risk_explain?: ClientDocumentRiskExplain | null;
}
