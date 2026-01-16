import { request } from "./http";
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

export type ClientMeResponse = {
  user: {
    id: string;
    email?: string | null;
    subject_type?: string | null;
  };
  org?: {
    id: string;
    name: string;
    inn?: string | null;
    status: string;
  } | null;
  membership: {
    roles: string[];
    status: string;
  };
  subscription?: {
    plan_code: string;
    status?: string | null;
    modules: Record<string, Record<string, unknown>>;
    limits: Record<string, Record<string, unknown>>;
  } | null;
  entitlements: {
    enabled_modules: string[];
    permissions: string[];
    limits: Record<string, Record<string, unknown>>;
    org_status: string;
  };
  org_status: string;
  dashboard?: ClientDashboardSnapshot | null;
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

const withToken = (user: AuthSession | null) => ({ token: user?.token, base: "core" as const });

export const fetchClientMe = (user: AuthSession | null) =>
  request<ClientMeResponse>("/client/me", { method: "GET" }, withToken(user));

export const createOrg = (user: AuthSession | null, payload: ClientOrgPayload) =>
  request<ClientOrgResponse>("/client/org", { method: "POST", body: JSON.stringify(payload) }, withToken(user));

export const updateOrg = (user: AuthSession | null, payload: ClientOrgPayload) =>
  request<ClientOrgResponse>("/client/org", { method: "PATCH", body: JSON.stringify(payload) }, withToken(user));

export const fetchPlans = (user: AuthSession | null) =>
  request<SubscriptionPlan[]>("/client/subscriptions/plans", { method: "GET" }, withToken(user));

export const selectSubscription = (user: AuthSession | null, payload: SubscriptionSelectPayload) =>
  request<ClientSubscriptionResponse>(
    "/client/subscription/select",
    { method: "POST", body: JSON.stringify(payload) },
    withToken(user),
  );

export const fetchSubscription = (user: AuthSession | null) =>
  request<ClientSubscriptionResponse>("/client/subscription", { method: "GET" }, withToken(user));

export const generateContract = (user: AuthSession | null) =>
  request<ContractInfo>("/client/contracts/generate", { method: "POST" }, withToken(user));

export const fetchCurrentContract = (user: AuthSession | null) =>
  request<ContractInfo>("/client/contracts/current", { method: "GET" }, withToken(user));

export const signContract = (user: AuthSession | null, payload: ContractSignPayload) =>
  request<ContractInfo>("/client/contracts/sign-simple", { method: "POST", body: JSON.stringify(payload) }, withToken(user));
