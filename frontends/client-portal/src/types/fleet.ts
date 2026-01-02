export type FleetCardStatus = "ACTIVE" | "BLOCKED" | "CLOSED" | string;

export interface FleetCard {
  id: string;
  card_alias?: string | null;
  masked_pan?: string | null;
  token_ref?: string | null;
  status?: FleetCardStatus;
  currency?: string | null;
  issued_at?: string | null;
  created_at?: string | null;
}

export type FleetGroupRole = "viewer" | "manager" | "admin" | string;

export interface FleetGroup {
  id: string;
  name: string;
  description?: string | null;
  created_at?: string | null;
  cards?: FleetCard[] | null;
  my_role?: FleetGroupRole | null;
  cards_count?: number | null;
}

export interface FleetEmployee {
  id: string;
  email: string;
  status?: string;
  created_at?: string | null;
}

export interface FleetAccess {
  id: string;
  employee_id: string;
  role: FleetGroupRole;
  created_at?: string | null;
  revoked_at?: string | null;
}

export interface FleetLimit {
  id: string;
  scope_type: string;
  scope_id?: string | null;
  period?: string | null;
  amount_limit?: number | string | null;
  volume_limit_liters?: number | string | null;
  categories?: Record<string, unknown> | null;
  stations_allowlist?: Record<string, unknown> | null;
  active?: boolean | null;
  effective_from?: string | null;
  created_at?: string | null;
}

export interface FleetTransaction {
  id: string;
  card_id?: string | null;
  occurred_at?: string | null;
  created_at?: string | null;
  amount?: number | string | null;
  currency?: string | null;
  volume_liters?: number | string | null;
  category?: string | null;
  merchant_name?: string | null;
  station_id?: string | null;
  location?: string | null;
  external_ref?: string | null;
}

export interface FleetSpendSummaryRow {
  key: string;
  amount: number | string;
}

export interface FleetSpendSummary {
  group_by: string;
  rows: FleetSpendSummaryRow[];
}

export interface FleetExportResponse {
  export_id?: string | null;
  url?: string | null;
  expires_in?: number | null;
}
