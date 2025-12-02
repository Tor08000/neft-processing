export interface ServiceHealth {
  service: string;
  status: "ok" | "error";
  details?: Record<string, unknown>;
}
