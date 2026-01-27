import { request } from "./http";
import type {
  AssignSubscriptionPayload,
  Achievement,
  Bonus,
  BonusRule,
  RoleEntitlement,
  Streak,
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

export async function listAchievements(token: string) {
  return request<Achievement[]>(`/subscriptions/gamification/achievements`, { method: "GET" }, token);
}

export async function createAchievement(token: string, payload: Omit<Achievement, "id">) {
  return request<Achievement>(
    `/subscriptions/gamification/achievements`,
    { method: "POST", body: JSON.stringify(payload) },
    token,
  );
}

export async function updateAchievement(token: string, achievementId: number, payload: Partial<Achievement>) {
  return request<Achievement>(
    `/subscriptions/gamification/achievements/${achievementId}`,
    { method: "PATCH", body: JSON.stringify(payload) },
    token,
  );
}

export async function listStreaks(token: string) {
  return request<Streak[]>(`/subscriptions/gamification/streaks`, { method: "GET" }, token);
}

export async function createStreak(token: string, payload: Omit<Streak, "id">) {
  return request<Streak>(`/subscriptions/gamification/streaks`, { method: "POST", body: JSON.stringify(payload) }, token);
}

export async function updateStreak(token: string, streakId: number, payload: Partial<Streak>) {
  return request<Streak>(
    `/subscriptions/gamification/streaks/${streakId}`,
    { method: "PATCH", body: JSON.stringify(payload) },
    token,
  );
}

export async function listBonuses(token: string) {
  return request<Bonus[]>(`/subscriptions/gamification/bonuses`, { method: "GET" }, token);
}

export async function createBonus(token: string, payload: Omit<Bonus, "id">) {
  return request<Bonus>(`/subscriptions/gamification/bonuses`, { method: "POST", body: JSON.stringify(payload) }, token);
}

export async function updateBonus(token: string, bonusId: number, payload: Partial<Bonus>) {
  return request<Bonus>(
    `/subscriptions/gamification/bonuses/${bonusId}`,
    { method: "PATCH", body: JSON.stringify(payload) },
    token,
  );
}

export async function assignSubscription(token: string, clientId: string, payload: AssignSubscriptionPayload) {
  return request<ClientSubscription>(
    `/v1/admin/clients/${clientId}/subscription/assign`,
    { method: "POST", body: JSON.stringify(payload) },
    token,
  );
}

export async function getClientSubscription(token: string, clientId: string) {
  return request<ClientSubscription>(`/v1/admin/clients/${clientId}/subscription`, { method: "GET" }, token);
}
