export type ControlLimitStatus = "OK" | "NEAR_LIMIT" | "EXCEEDED";

export interface ClientLimitItem {
  id?: string | null;
  label?: string | null;
  type?: string | null;
  period?: string | null;
  limit?: number | null;
  used?: number | null;
  status?: ControlLimitStatus | null;
  partner?: string | null;
  service?: string | null;
  station?: string | null;
}

export interface ClientLimitsResponse {
  amount_limits?: ClientLimitItem[] | null;
  operation_limits?: ClientLimitItem[] | null;
  service_limits?: ClientLimitItem[] | null;
  partner_limits?: ClientLimitItem[] | null;
  station_limits?: ClientLimitItem[] | null;
  items?: ClientLimitItem[] | null;
  status?: ControlLimitStatus | null;
}

export interface LimitChangeRequestPayload {
  limit_type: string;
  new_value: number;
  comment?: string | null;
}

export interface LimitChangeRequestResponse {
  status: string;
  request_id?: string | null;
  message?: string | null;
}

export interface ClientUserSummary {
  id: string;
  email: string;
  role: string;
  status?: string | null;
  last_login?: string | null;
}

export interface ClientUsersResponse {
  items?: ClientUserSummary[] | null;
}

export interface CreateClientUserPayload {
  email: string;
  role: string;
}

export interface UpdateClientUserPayload {
  roles: string[];
}

export interface ClientServiceItem {
  id: string;
  partner?: string | null;
  service?: string | null;
  status?: string | null;
  restrictions?: string | null;
}

export interface ClientServicesResponse {
  items?: ClientServiceItem[] | null;
}

export interface ClientFeatureItem {
  key: string;
  description?: string | null;
  status?: string | null;
  scope?: string | null;
}

export interface ClientFeaturesResponse {
  items?: ClientFeatureItem[] | null;
}

export interface ControlToggleResponse {
  status?: string | null;
  reason?: string | null;
}
