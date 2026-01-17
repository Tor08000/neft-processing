export type HelpdeskProvider = "zendesk" | "jira_sm";

export type HelpdeskIntegrationStatus = "ACTIVE" | "DISABLED";

export interface HelpdeskIntegrationConfig {
  base_url: string;
  api_email?: string | null;
  api_token?: string | null;
  project_id?: string | null;
  brand_id?: string | null;
}

export interface HelpdeskIntegrationPayload {
  provider: HelpdeskProvider;
  config: HelpdeskIntegrationConfig;
}

export interface HelpdeskIntegrationPatch {
  provider?: HelpdeskProvider;
  config?: HelpdeskIntegrationConfig;
}

export interface HelpdeskIntegration {
  id: string;
  org_id: string;
  provider: HelpdeskProvider;
  status: HelpdeskIntegrationStatus;
  base_url?: string | null;
  project_id?: string | null;
  brand_id?: string | null;
  last_error?: string | null;
  created_at: string;
  updated_at: string;
}

export interface HelpdeskIntegrationResponse {
  integration: HelpdeskIntegration | null;
}

export type HelpdeskTicketLinkStatus = "LINKED" | "FAILED";

export interface HelpdeskTicketLink {
  id: string;
  org_id: string;
  internal_ticket_id: string;
  provider: HelpdeskProvider;
  external_ticket_id?: string | null;
  external_url?: string | null;
  status: HelpdeskTicketLinkStatus;
  last_sync_at?: string | null;
}

export interface HelpdeskTicketLinkResponse {
  link: HelpdeskTicketLink | null;
}
