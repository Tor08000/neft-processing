import { request } from "./http";
import { withToken } from "./token";
import type { AuthSession } from "./types";
import type { ClientSubscription, GamificationSummary, SubscriptionBenefits } from "../types/subscriptions";

export function fetchMySubscription(user: AuthSession | null) {
  return request<ClientSubscription>("/subscriptions/me", { method: "GET" }, { ...withToken(user), base: "core_root" });
}

export function fetchSubscriptionBenefits(user: AuthSession | null) {
  return request<SubscriptionBenefits>("/subscriptions/me/benefits", { method: "GET" }, { ...withToken(user), base: "core_root" });
}

export function fetchGamificationSummary(user: AuthSession | null) {
  return request<GamificationSummary>("/subscriptions/me/gamification", { method: "GET" }, { ...withToken(user), base: "core_root" });
}
