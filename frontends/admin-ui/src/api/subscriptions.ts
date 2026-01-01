import { request } from "./http";
import type {
  AssignSubscriptionPayload,
  BonusRule,
  RoleEntitlement,
  SubscriptionPlan,
  SubscriptionPlanCreate,
  SubscriptionPlanModule,
  SubscriptionPlanUpdate,
  ClientSubscription,
} from "../types/subscriptions";

export async function listSubscriptionPlans(token: string, activeOnly?: boolean) {
  const query = activeOnly ? "?active_only=true" : "";
  return request<SubscriptionPlan[]>(`/subscriptions/plans${query}`, { method: "GET" }, token);
}

export async function getSubscriptionPlan(token: string, planId: string) {
  return request<SubscriptionPlan>(`/subscriptions/plans/${planId}`, { method: "GET" }, token);
}

export async function createSubscriptionPlan(token: string, payload: SubscriptionPlanCreate) {
  return request<SubscriptionPlan>(`/subscriptions/plans`, { method: "POST", body: JSON.stringify(payload) }, token);
}

export async function updateSubscriptionPlan(token: string, planId: string, payload: SubscriptionPlanUpdate) {
  return request<SubscriptionPlan>(`/subscriptions/plans/${planId}`, { method: "PATCH", body: JSON.stringify(payload) }, token);
}

export async function updateSubscriptionPlanModules(token: string, planId: string, payload: SubscriptionPlanModule[]) {
  return request<SubscriptionPlanModule[]>(
    `/subscriptions/plans/${planId}/modules`,
    { method: "PATCH", body: JSON.stringify(payload) },
    token,
  );
}

export async function updateSubscriptionPlanRoles(token: string, planId: string, payload: RoleEntitlement[]) {
  return request<RoleEntitlement[]>(
    `/subscriptions/plans/${planId}/roles`,
    { method: "PATCH", body: JSON.stringify(payload) },
    token,
  );
}

export async function listBonusRules(token: string, planId?: string) {
  const query = planId ? `?plan_id=${encodeURIComponent(planId)}` : "";
  return request<BonusRule[]>(`/subscriptions/bonus-rules${query}`, { method: "GET" }, token);
}

export async function createBonusRule(token: string, payload: Omit<BonusRule, "id">) {
  return request<BonusRule>(`/subscriptions/bonus-rules`, { method: "POST", body: JSON.stringify(payload) }, token);
}

export async function updateBonusRule(token: string, ruleId: number, payload: Partial<BonusRule>) {
  return request<BonusRule>(
    `/subscriptions/bonus-rules/${ruleId}`,
    { method: "PATCH", body: JSON.stringify(payload) },
    token,
  );
}

export async function assignSubscription(token: string, clientId: string, payload: AssignSubscriptionPayload) {
  return request<ClientSubscription>(
    `/admin/clients/${clientId}/subscription/assign`,
    { method: "POST", body: JSON.stringify(payload) },
    token,
  );
}

export async function getClientSubscription(token: string, clientId: string) {
  return request<ClientSubscription>(`/admin/clients/${clientId}/subscription`, { method: "GET" }, token);
}
