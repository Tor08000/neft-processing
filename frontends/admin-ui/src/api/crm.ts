import { request } from "./http";
import type {
  CrmClient,
  CrmContract,
  CrmDecisionContext,
  CrmFeatureFlag,
  CrmListResponse,
  CrmProfile,
  CrmRiskProfile,
  CrmSubscription,
  CrmTariff,
} from "../types/crm";

const CRM_BASE = "/crm";
const CRM_HEADERS = { "X-CRM-Version": "1" } as const;

type QueryValue = string | number | boolean | undefined | null;

type ClientPayload = Partial<CrmClient> & { client_id?: string; id?: string };
type ContractPayload = Partial<CrmContract>;
type SubscriptionPayload = Partial<CrmSubscription>;
type TariffPayload = Partial<CrmTariff>;

function buildQuery(params?: Record<string, QueryValue>): string {
  if (!params) return "";
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      query.set(key, String(value));
    }
  });
  const qs = query.toString();
  return qs ? `?${qs}` : "";
}

function crmRequest<T>(token: string, path: string, init: RequestInit = {}) {
  return request<T>(
    path,
    {
      ...init,
      headers: {
        ...CRM_HEADERS,
        ...(init.headers as Record<string, string> | undefined),
      },
    },
    { token },
  );
}

function normalizeIsoDate(value?: string | null): string | undefined {
  if (!value) return undefined;
  if (value.includes("T")) return value;
  return `${value}T00:00:00Z`;
}

function asListResponse<T>(items: T[]): CrmListResponse<T> {
  return { items };
}

function toClient(raw: Record<string, unknown>): CrmClient {
  return {
    id: String(raw.id),
    client_id: String(raw.id),
    tenant_id: Number(raw.tenant_id),
    legal_name: String(raw.legal_name ?? ""),
    tax_id: (raw.tax_id as string | null | undefined) ?? null,
    kpp: (raw.kpp as string | null | undefined) ?? null,
    status: String(raw.status ?? ""),
    country: String(raw.country ?? ""),
    timezone: String(raw.timezone ?? ""),
    created_at: (raw.created_at as string | null | undefined) ?? null,
    updated_at: (raw.updated_at as string | null | undefined) ?? null,
    meta: (raw.meta as Record<string, unknown> | null | undefined) ?? null,
  };
}

function toContract(raw: Record<string, unknown>): CrmContract {
  return {
    id: String(raw.id),
    contract_id: String(raw.id),
    tenant_id: Number(raw.tenant_id),
    contract_number: String(raw.contract_number ?? ""),
    client_id: String(raw.client_id ?? ""),
    status: String(raw.status ?? ""),
    valid_from: (raw.valid_from as string | null | undefined) ?? null,
    valid_to: (raw.valid_to as string | null | undefined) ?? null,
    billing_mode: (raw.billing_mode as string | null | undefined) ?? null,
    currency: (raw.currency as string | null | undefined) ?? null,
    risk_profile_id: (raw.risk_profile_id as string | null | undefined) ?? null,
    limit_profile_id: (raw.limit_profile_id as string | null | undefined) ?? null,
    documents_required: (raw.documents_required as boolean | null | undefined) ?? null,
    crm_contract_version: (raw.crm_contract_version as number | null | undefined) ?? null,
    created_at: (raw.created_at as string | null | undefined) ?? null,
    meta: (raw.meta as Record<string, unknown> | null | undefined) ?? null,
  };
}

function toTariff(raw: Record<string, unknown>): CrmTariff {
  return {
    id: String(raw.id),
    tariff_id: String(raw.id),
    name: String(raw.name ?? ""),
    description: (raw.description as string | null | undefined) ?? null,
    status: String(raw.status ?? ""),
    billing_period: String(raw.billing_period ?? ""),
    base_fee_minor: Number(raw.base_fee_minor ?? 0),
    currency: String(raw.currency ?? "RUB"),
    features: (raw.features as Record<string, boolean> | null | undefined) ?? null,
    limits_defaults: (raw.limits_defaults as Record<string, unknown> | null | undefined) ?? null,
    definition: (raw.definition as Record<string, unknown> | null | undefined) ?? null,
    created_at: (raw.created_at as string | null | undefined) ?? null,
  };
}

function toSubscription(raw: Record<string, unknown>): CrmSubscription {
  return {
    id: String(raw.id),
    subscription_id: String(raw.id),
    tenant_id: Number(raw.tenant_id),
    client_id: String(raw.client_id ?? ""),
    tariff_plan_id: String(raw.tariff_plan_id ?? ""),
    status: String(raw.status ?? ""),
    billing_cycle: (raw.billing_cycle as string | null | undefined) ?? null,
    billing_day: (raw.billing_day as number | null | undefined) ?? null,
    started_at: (raw.started_at as string | null | undefined) ?? null,
    paused_at: (raw.paused_at as string | null | undefined) ?? null,
    ended_at: (raw.ended_at as string | null | undefined) ?? null,
    meta: (raw.meta as Record<string, unknown> | null | undefined) ?? null,
    created_at: (raw.created_at as string | null | undefined) ?? null,
    updated_at: (raw.updated_at as string | null | undefined) ?? null,
  };
}

function toProfile(raw: Record<string, unknown>): CrmProfile {
  return {
    id: String(raw.id),
    tenant_id: raw.tenant_id !== undefined ? Number(raw.tenant_id) : null,
    name: (raw.name as string | null | undefined) ?? null,
    status: (raw.status as string | null | undefined) ?? null,
    definition: (raw.definition as Record<string, unknown> | null | undefined) ?? null,
    created_at: (raw.created_at as string | null | undefined) ?? null,
  };
}

function toRiskProfile(raw: Record<string, unknown>): CrmRiskProfile {
  return {
    ...toProfile(raw),
    risk_policy_id: (raw.risk_policy_id as string | null | undefined) ?? null,
    threshold_set_id: (raw.threshold_set_id as string | null | undefined) ?? null,
    shadow_enabled: (raw.shadow_enabled as boolean | null | undefined) ?? null,
  };
}

function toFeatureFlag(raw: Record<string, unknown>): CrmFeatureFlag {
  return {
    id: (raw.id as string | null | undefined) ?? null,
    tenant_id: raw.tenant_id !== undefined ? Number(raw.tenant_id) : null,
    client_id: (raw.client_id as string | null | undefined) ?? null,
    feature: String(raw.feature ?? ""),
    enabled: Boolean(raw.enabled),
    updated_at: (raw.updated_at as string | null | undefined) ?? null,
    updated_by: (raw.updated_by as string | null | undefined) ?? null,
  };
}

function toFeatureRecord(items: CrmFeatureFlag[]): Record<string, boolean> {
  return items.reduce<Record<string, boolean>>((acc, item) => {
    acc[item.feature] = item.enabled;
    return acc;
  }, {});
}

function serializeClientPayload(payload: ClientPayload): Record<string, unknown> {
  return {
    id: payload.client_id ?? payload.id,
    tenant_id: payload.tenant_id,
    legal_name: payload.legal_name,
    tax_id: payload.tax_id ?? undefined,
    kpp: payload.kpp ?? undefined,
    country: payload.country,
    timezone: payload.timezone,
    status: payload.status ?? undefined,
    meta: payload.meta ?? undefined,
  };
}

function serializeContractPayload(payload: ContractPayload): Record<string, unknown> {
  return {
    tenant_id: payload.tenant_id,
    contract_number: payload.contract_number,
    status: payload.status ?? undefined,
    valid_from: normalizeIsoDate(payload.valid_from),
    valid_to: normalizeIsoDate(payload.valid_to),
    billing_mode: payload.billing_mode ?? undefined,
    currency: payload.currency ?? undefined,
    risk_profile_id: payload.risk_profile_id ?? undefined,
    limit_profile_id: payload.limit_profile_id ?? undefined,
    documents_required: payload.documents_required ?? false,
    meta: payload.meta ?? undefined,
  };
}

function serializeSubscriptionPayload(payload: SubscriptionPayload): Record<string, unknown> {
  return {
    tenant_id: payload.tenant_id,
    tariff_plan_id: payload.tariff_plan_id,
    status: payload.status ?? undefined,
    billing_cycle: payload.billing_cycle ?? undefined,
    billing_day: payload.billing_day ?? undefined,
    started_at: normalizeIsoDate(payload.started_at),
    paused_at: normalizeIsoDate(payload.paused_at),
    ended_at: normalizeIsoDate(payload.ended_at),
    meta: payload.meta ?? undefined,
  };
}

function serializeTariffPayload(payload: TariffPayload): Record<string, unknown> {
  return {
    id: payload.id ?? payload.tariff_id,
    name: payload.name,
    description: payload.description ?? undefined,
    status: payload.status ?? undefined,
    billing_period: payload.billing_period,
    base_fee_minor: payload.base_fee_minor,
    currency: payload.currency,
    features: payload.features ?? undefined,
    limits_defaults: payload.limits_defaults ?? undefined,
    definition: payload.definition ?? undefined,
  };
}

export async function listClients(token: string, params?: Record<string, QueryValue>) {
  const items = await crmRequest<Record<string, unknown>[]>(token, `${CRM_BASE}/clients${buildQuery(params)}`, {
    method: "GET",
  });
  return asListResponse(items.map(toClient));
}

export async function createClient(token: string, payload: ClientPayload) {
  const client = await crmRequest<Record<string, unknown>>(
    token,
    `${CRM_BASE}/clients`,
    { method: "POST", body: JSON.stringify(serializeClientPayload(payload)) },
  );
  return toClient(client);
}

export async function getClient(token: string, clientId: string) {
  const client = await crmRequest<Record<string, unknown>>(token, `${CRM_BASE}/clients/${clientId}`, { method: "GET" });
  return toClient(client);
}

export async function getClientDecisionContext(token: string, clientId: string) {
  const context = await crmRequest<Record<string, unknown>>(token, `${CRM_BASE}/clients/${clientId}/decision-context`, {
    method: "GET",
  });
  return {
    client_id: String(context.client_id),
    tenant_id: Number(context.tenant_id),
    active_contract: context.active_contract ? toContract(context.active_contract as Record<string, unknown>) : null,
    tariff: context.tariff ? toTariff(context.tariff as Record<string, unknown>) : null,
    feature_flags: Array.isArray(context.feature_flags)
      ? (context.feature_flags as Record<string, unknown>[]).map(toFeatureFlag)
      : [],
    risk_profile: context.risk_profile ? toRiskProfile(context.risk_profile as Record<string, unknown>) : null,
    limit_profile: context.limit_profile ? toProfile(context.limit_profile as Record<string, unknown>) : null,
    enforcement_flags: (context.enforcement_flags as Record<string, boolean> | undefined) ?? {},
  } satisfies CrmDecisionContext;
}

export async function updateClient(token: string, clientId: string, payload: ClientPayload) {
  const serialized = serializeClientPayload(payload);
  delete serialized.id;
  delete serialized.tenant_id;
  const client = await crmRequest<Record<string, unknown>>(
    token,
    `${CRM_BASE}/clients/${clientId}`,
    { method: "PATCH", body: JSON.stringify(serialized) },
  );
  return toClient(client);
}

export async function listContracts(token: string, params?: Record<string, QueryValue>) {
  const items = await crmRequest<Record<string, unknown>[]>(
    token,
    `${CRM_BASE}/contracts${buildQuery(params)}`,
    { method: "GET" },
  );
  return asListResponse(items.map(toContract));
}

export async function getContract(token: string, contractId: string) {
  const contract = await crmRequest<Record<string, unknown>>(token, `${CRM_BASE}/contracts/${contractId}`, {
    method: "GET",
  });
  return toContract(contract);
}

export async function createContract(token: string, clientId: string, payload: ContractPayload) {
  const contract = await crmRequest<Record<string, unknown>>(
    token,
    `${CRM_BASE}/clients/${clientId}/contracts`,
    { method: "POST", body: JSON.stringify(serializeContractPayload(payload)) },
  );
  return toContract(contract);
}

export async function updateContract(token: string, contractId: string, payload: ContractPayload) {
  const serialized = serializeContractPayload(payload);
  delete serialized.tenant_id;
  const contract = await crmRequest<Record<string, unknown>>(
    token,
    `${CRM_BASE}/contracts/${contractId}`,
    { method: "PATCH", body: JSON.stringify(serialized) },
  );
  return toContract(contract);
}

export async function activateContract(token: string, contractId: string) {
  const contract = await crmRequest<Record<string, unknown>>(token, `${CRM_BASE}/contracts/${contractId}/activate`, {
    method: "POST",
  });
  return toContract(contract);
}

export async function pauseContract(token: string, contractId: string) {
  const contract = await crmRequest<Record<string, unknown>>(token, `${CRM_BASE}/contracts/${contractId}/pause`, {
    method: "POST",
  });
  return toContract(contract);
}

export async function terminateContract(token: string, contractId: string) {
  const contract = await crmRequest<Record<string, unknown>>(token, `${CRM_BASE}/contracts/${contractId}/terminate`, {
    method: "POST",
  });
  return toContract(contract);
}

export async function applyContract(token: string, contractId: string) {
  return crmRequest<Record<string, unknown>>(token, `${CRM_BASE}/contracts/${contractId}/apply`, { method: "POST" });
}

export async function listTariffs(token: string, params?: Record<string, QueryValue>) {
  const items = await crmRequest<Record<string, unknown>[]>(
    token,
    `${CRM_BASE}/tariffs${buildQuery(params)}`,
    { method: "GET" },
  );
  return asListResponse(items.map(toTariff));
}

export async function getTariff(token: string, tariffId: string) {
  const tariff = await crmRequest<Record<string, unknown>>(token, `${CRM_BASE}/tariffs/${tariffId}`, {
    method: "GET",
  });
  return toTariff(tariff);
}

export async function createTariff(token: string, payload: TariffPayload) {
  const tariff = await crmRequest<Record<string, unknown>>(
    token,
    `${CRM_BASE}/tariffs`,
    { method: "POST", body: JSON.stringify(serializeTariffPayload(payload)) },
  );
  return toTariff(tariff);
}

export async function updateTariff(token: string, tariffId: string, payload: TariffPayload) {
  const serialized = serializeTariffPayload(payload);
  delete serialized.id;
  const tariff = await crmRequest<Record<string, unknown>>(
    token,
    `${CRM_BASE}/tariffs/${tariffId}`,
    { method: "PATCH", body: JSON.stringify(serialized) },
  );
  return toTariff(tariff);
}

export async function listSubscriptions(token: string, params?: Record<string, QueryValue>) {
  const items = await crmRequest<Record<string, unknown>[]>(
    token,
    `${CRM_BASE}/subscriptions${buildQuery(params)}`,
    { method: "GET" },
  );
  return asListResponse(items.map(toSubscription));
}

export async function getSubscription(token: string, subscriptionId: string) {
  const subscription = await crmRequest<Record<string, unknown>>(token, `${CRM_BASE}/subscriptions/${subscriptionId}`, {
    method: "GET",
  });
  return toSubscription(subscription);
}

export async function createSubscription(token: string, clientId: string, payload: SubscriptionPayload) {
  const subscription = await crmRequest<Record<string, unknown>>(
    token,
    `${CRM_BASE}/clients/${clientId}/subscriptions`,
    { method: "POST", body: JSON.stringify(serializeSubscriptionPayload(payload)) },
  );
  return toSubscription(subscription);
}

export async function updateSubscription(token: string, subscriptionId: string, payload: SubscriptionPayload) {
  const serialized = serializeSubscriptionPayload(payload);
  delete serialized.tenant_id;
  delete serialized.tariff_plan_id;
  const subscription = await crmRequest<Record<string, unknown>>(
    token,
    `${CRM_BASE}/subscriptions/${subscriptionId}`,
    { method: "PATCH", body: JSON.stringify(serialized) },
  );
  return toSubscription(subscription);
}

export async function pauseSubscription(token: string, subscriptionId: string) {
  const subscription = await crmRequest<Record<string, unknown>>(token, `${CRM_BASE}/subscriptions/${subscriptionId}/pause`, {
    method: "POST",
  });
  return toSubscription(subscription);
}

export async function resumeSubscription(token: string, subscriptionId: string) {
  const subscription = await crmRequest<Record<string, unknown>>(token, `${CRM_BASE}/subscriptions/${subscriptionId}/resume`, {
    method: "POST",
  });
  return toSubscription(subscription);
}

export async function cancelSubscription(token: string, subscriptionId: string) {
  const subscription = await crmRequest<Record<string, unknown>>(token, `${CRM_BASE}/subscriptions/${subscriptionId}/cancel`, {
    method: "POST",
  });
  return toSubscription(subscription);
}

export async function previewSubscriptionBilling(token: string, subscriptionId: string, params: { period_id: string }) {
  return crmRequest<Record<string, unknown>>(
    token,
    `${CRM_BASE}/subscriptions/${subscriptionId}/preview-billing${buildQuery({ period_id: params.period_id })}`,
    { method: "POST" },
  );
}

export async function subscriptionCfoExplain(token: string, subscriptionId: string, params: { period_id: string }) {
  return crmRequest<Record<string, unknown>>(
    token,
    `${CRM_BASE}/subscriptions/${subscriptionId}/cfo-explain${buildQuery({ period_id: params.period_id })}`,
    { method: "GET" },
  );
}

export async function getClientFeatures(token: string, clientId: string) {
  const items = await crmRequest<Record<string, unknown>[]>(
    token,
    `${CRM_BASE}/clients/${clientId}/features`,
    { method: "GET" },
  );
  return toFeatureRecord(items.map(toFeatureFlag));
}

export async function enableFeature(token: string, clientId: string, feature: string) {
  await crmRequest<Record<string, unknown>>(
    token,
    `${CRM_BASE}/clients/${clientId}/features/${feature}/enable`,
    { method: "POST" },
  );
  return getClientFeatures(token, clientId);
}

export async function disableFeature(token: string, clientId: string, feature: string) {
  await crmRequest<Record<string, unknown>>(
    token,
    `${CRM_BASE}/clients/${clientId}/features/${feature}/disable`,
    { method: "POST" },
  );
  return getClientFeatures(token, clientId);
}

export async function listLimitProfiles(token: string) {
  const items = await crmRequest<Record<string, unknown>[]>(token, `${CRM_BASE}/limit-profiles`, { method: "GET" });
  return asListResponse(items.map(toProfile));
}

export async function listRiskProfiles(token: string) {
  const items = await crmRequest<Record<string, unknown>[]>(token, `${CRM_BASE}/risk-profiles`, { method: "GET" });
  return asListResponse(items.map(toRiskProfile));
}
