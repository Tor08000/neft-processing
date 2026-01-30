import { ApiError, CORE_API_BASE, UnauthorizedError, request } from "./http";
import type { AuthSession } from "./types";

export type ClientDashboardSnapshot = {
  cards?: {
    total?: number | null;
    active?: number | null;
    blocked?: number | null;
    mine?: number | null;
    available_to_issue?: number | null;
  } | null;
  users?: {
    total?: number | null;
    active?: number | null;
    invited?: number | null;
    disabled?: number | null;
  } | null;
  documents?: Array<{
    id: string;
    type: string;
    status: string;
    date: string;
  }> | null;
  activity?: Array<{
    id: string;
    message: string;
    created_at: string;
  }> | null;
};

export type PortalMeResponse = {
  actor_type?: string;
  context?: string | null;
  user: {
    id: string;
    email?: string | null;
    subject_type?: string | null;
    timezone?: string | null;
  };
  org?: {
    id: string;
    name: string;
    inn?: string | null;
    status: string;
    timezone?: string | null;
  } | null;
  org_status?: string | null;
  org_roles: string[];
  user_roles: string[];
  roles?: string[] | null;
  memberships?: string[] | null;
  flags?: Record<string, unknown> | null;
  legal?: {
    required_count: number;
    accepted: boolean;
    missing: string[];
    required_enabled?: boolean | null;
  } | null;
  modules?: Record<string, unknown> | null;
  features?: {
    onboarding_enabled?: boolean;
    legal_gate_enabled?: boolean;
  } | null;
  gating?: {
    onboarding_enabled: boolean;
    legal_gate_enabled: boolean;
  } | null;
  subscription?: {
    plan_code?: string | null;
    status?: string | null;
    billing_cycle?: string | null;
    support_plan?: string | null;
    slo_tier?: string | null;
    addons?: Array<Record<string, unknown>> | null;
  } | null;
  entitlements_snapshot?: Record<string, unknown> | null;
  capabilities: string[];
  nav_sections?: Array<{ code: string; label: string }> | null;
  dashboard?: ClientDashboardSnapshot | null;
  partner?: {
    status?: string | null;
    profile?: {
      display_name?: string | null;
      contacts_json?: Record<string, unknown> | null;
      meta_json?: Record<string, unknown> | null;
    } | null;
  } | null;
  access_state: string;
  access_reason?: string | null;
  billing?: {
    overdue_invoices?: Array<{
      id: number | string;
      number?: string | null;
      amount?: number | string | null;
      currency?: string | null;
      due_at?: string | null;
      download_url?: string | null;
      status?: string | null;
    }>;
    next_action?: string | null;
  } | null;
};

export type ClientOrgPayload = {
  org_type: "LEGAL" | "IP" | "INDIVIDUAL";
  name: string;
  inn?: string | null;
  kpp?: string | null;
  ogrn?: string | null;
  address?: string | null;
};

export type ClientOrgResponse = ClientOrgPayload & {
  id: string;
  status: string;
};

export type ContractInfo = {
  contract_id: string;
  status: string;
  pdf_url?: string | null;
  summary?: string | null;
  version?: number | null;
};

export type ContractSignPayload = {
  otp: string;
};

export type SubscriptionPlan = {
  id: string;
  code: string;
  title: string;
  description?: string | null;
  is_active: boolean;
  billing_period_months?: number | null;
  price_cents?: number | null;
  currency?: string | null;
  modules?: Array<{
    id?: string;
    module_code: string;
    enabled: boolean;
    tier?: string | null;
    limits?: Record<string, unknown> | null;
  }>;
};

export type SubscriptionSelectPayload = {
  plan_code: string;
  auto_renew?: boolean;
  duration_months?: number | null;
};

export type ClientSubscriptionResponse = {
  plan_code: string;
  status?: string | null;
  modules: Record<string, Record<string, unknown>>;
  limits: Record<string, Record<string, unknown>>;
};

export type AuditEventSummary = {
  id: string;
  created_at: string;
  org_id?: string | null;
  actor_user_id?: string | null;
  actor_label?: string | null;
  action?: string | null;
  entity_type?: string | null;
  entity_id?: string | null;
  entity_label?: string | null;
  request_id?: string | null;
  ip?: string | null;
  ua?: string | null;
  result?: string | null;
  summary?: string | null;
};

export type AuditEventsResponse = {
  items: AuditEventSummary[];
  next_cursor?: string | null;
};

export type AuditEventsFilters = {
  from?: string;
  to?: string;
  action?: string[];
  actor?: string;
  entity_type?: string;
  entity_id?: string;
  request_id?: string;
  limit?: number;
  cursor?: string;
};

const withToken = (user: AuthSession | null) => ({ token: user?.token, base: "core" as const });

export const PORTAL_ME_PATH = "/portal/me";

export const fetchClientMe = (user: AuthSession | null) =>
  request<PortalMeResponse>(PORTAL_ME_PATH, { method: "GET" }, withToken(user));

export type ClientTimezoneUpdateResponse = {
  id: string;
  email?: string | null;
  subject_type?: string | null;
  timezone?: string | null;
};

export const updateClientTimezone = (user: AuthSession | null, timezone: string) =>
  request<ClientTimezoneUpdateResponse>(
    "/client/account",
    { method: "PATCH", body: JSON.stringify({ timezone }) },
    withToken(user),
  );

export const createOrg = (user: AuthSession | null, payload: ClientOrgPayload) =>
  request<ClientOrgResponse>("/client/onboarding/profile", { method: "POST", body: JSON.stringify(payload) }, withToken(user));

export const updateOrg = (user: AuthSession | null, payload: ClientOrgPayload) =>
  request<ClientOrgResponse>("/client/org", { method: "PATCH", body: JSON.stringify(payload) }, withToken(user));

export const fetchPlans = (user: AuthSession | null) =>
  request<SubscriptionPlan[]>("/client/plans", { method: "GET" }, withToken(user));

export const selectSubscription = (user: AuthSession | null, payload: SubscriptionSelectPayload) =>
  request<ClientSubscriptionResponse>("/client/subscription", { method: "POST", body: JSON.stringify(payload) }, withToken(user));

export const fetchSubscription = (user: AuthSession | null) =>
  request<ClientSubscriptionResponse>("/client/subscription", { method: "GET" }, withToken(user));

export const generateContract = (user: AuthSession | null) =>
  request<ContractInfo>("/client/contracts/generate", { method: "POST" }, withToken(user));

export const fetchCurrentContract = (user: AuthSession | null) =>
  request<ContractInfo>("/client/contracts/current", { method: "GET" }, withToken(user));

export const signContract = (user: AuthSession | null, contractId: string, payload: ContractSignPayload) =>
  request<ContractInfo>(
    `/client/contracts/${contractId}/sign`,
    { method: "POST", body: JSON.stringify(payload) },
    withToken(user),
  );

export const buildAuditEventsQuery = (filters: AuditEventsFilters = {}): string => {
  const search = new URLSearchParams();
  if (filters.from) search.set("from", filters.from);
  if (filters.to) search.set("to", filters.to);
  if (filters.actor) search.set("actor", filters.actor);
  if (filters.entity_type) search.set("entity_type", filters.entity_type);
  if (filters.entity_id) search.set("entity_id", filters.entity_id);
  if (filters.request_id) search.set("request_id", filters.request_id);
  if (filters.limit) search.set("limit", String(filters.limit));
  if (filters.cursor) search.set("cursor", filters.cursor);
  if (filters.action?.length) {
    filters.action.forEach((item) => search.append("action", item));
  }
  return search.toString();
};

export const getAuditEvents = (user: AuthSession | null, filters: AuditEventsFilters = {}) => {
  const query = buildAuditEventsQuery(filters);
  const path = query ? `/client/audit/events?${query}` : "/client/audit/events";
  return request<AuditEventsResponse>(path, { method: "GET" }, withToken(user));
};

const parseFilename = (header: string | null): string | null => {
  if (!header) return null;
  const match = header.match(/filename=\"?([^\";]+)\"?/i);
  return match?.[1] ?? null;
};

export const exportAuditEvents = async (user: AuthSession | null, filters: AuditEventsFilters = {}): Promise<void> => {
  const token = user?.token;
  const headers: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {};
  const query = buildAuditEventsQuery(filters);
  const suffix = query ? `?${query}` : "";
  const response = await fetch(`${CORE_API_BASE}/client/audit/events/export${suffix}`, { headers });
  if (response.status === 401) {
    throw new UnauthorizedError();
  }
  if (!response.ok) {
    const correlationId = response.headers.get("x-correlation-id") ?? response.headers.get("x-request-id");
    throw new ApiError(await response.text(), response.status, correlationId, null, null);
  }
  const blob = await response.blob();
  const filename = parseFilename(response.headers.get("Content-Disposition")) ?? "audit_events.csv";
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  window.URL.revokeObjectURL(url);
};
