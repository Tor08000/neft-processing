export type ServiceSloService = "exports" | "email" | "support" | "schedules";
export type ServiceSloMetric = "latency" | "success_rate";
export type ServiceSloWindow = "7d" | "30d";
export type ServiceSloBreachStatus = "OPEN" | "ACKED" | "RESOLVED";

export interface ServiceSloItem {
  id: string;
  org_id: string;
  service: ServiceSloService;
  metric: ServiceSloMetric;
  objective_json: Record<string, unknown>;
  objective?: string | null;
  window: ServiceSloWindow;
  enabled: boolean;
  breach_status?: ServiceSloBreachStatus | null;
  breached_at?: string | null;
  window_start?: string | null;
  window_end?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ServiceSloListResponse {
  items: ServiceSloItem[];
}

export interface ServiceSloBreachItem {
  service: ServiceSloService;
  metric: ServiceSloMetric;
  objective: string;
  window: ServiceSloWindow;
  observed: string;
  status: ServiceSloBreachStatus;
  breached_at: string;
}

export interface ServiceSloBreachListResponse {
  items: ServiceSloBreachItem[];
}
