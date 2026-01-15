import { request } from "./http";
import type { CardLimit, ClientCard, ClientCardsResponse } from "../types/cards";
import type { AuthSession } from "./types";

const withToken = (user: AuthSession | null): string | undefined => user?.token;

type ApiCardLimit = {
  limit_type: string;
  amount: number;
  currency: string;
};

type ApiCard = {
  id: string;
  status: string;
  pan_masked?: string | null;
  limits: ApiCardLimit[];
};

const normalizeLimitWindow = (limitType: string): string => {
  if (limitType.includes("DAILY")) return "DAY";
  if (limitType.includes("MONTH")) return "MONTH";
  return "CUSTOM";
};

const toClientCard = (card: ApiCard): ClientCard => ({
  id: card.id,
  status: card.status,
  pan_masked: card.pan_masked,
  limits: card.limits.map((limit) => ({
    type: limit.limit_type,
    value: limit.amount,
    window: normalizeLimitWindow(limit.limit_type),
  })),
});

export async function fetchCards(user: AuthSession | null): Promise<ClientCardsResponse> {
  const response = await request<{ items: ApiCard[] }>("/client/cards", { method: "GET" }, withToken(user));
  return { items: response.items.map(toClientCard) };
}

export async function fetchCard(cardId: string, user: AuthSession | null): Promise<ClientCard> {
  const response = await request<ApiCard>(`/client/cards/${cardId}`, { method: "GET" }, withToken(user));
  return toClientCard(response);
}

export async function blockCard(cardId: string, user: AuthSession | null): Promise<{ status: string }>
{
  return request<{ status: string }>(
    `/client/cards/${cardId}`,
    { method: "PATCH", body: JSON.stringify({ status: "BLOCKED" }) },
    withToken(user),
  );
}

export async function unblockCard(
  cardId: string,
  user: AuthSession | null,
): Promise<{ status: string }> {
  return request<{ status: string }>(
    `/client/cards/${cardId}`,
    { method: "PATCH", body: JSON.stringify({ status: "ACTIVE" }) },
    withToken(user),
  );
}

export async function updateCardLimit(
  cardId: string,
  payload: CardLimit,
  user: AuthSession | null,
): Promise<ClientCard> {
  const response = await request<ApiCard>(
    `/client/cards/${cardId}/limits`,
    {
      method: "PATCH",
      body: JSON.stringify({ limit_type: payload.type, amount: payload.value, currency: "RUB" }),
    },
    withToken(user),
  );
  return toClientCard(response);
}

export async function fetchCardAccess(cardId: string, user: AuthSession | null) {
  return request<{ items: { user_id: string; scope: string; effective_from?: string | null }[] }>(
    `/client/cards/${cardId}/access`,
    { method: "GET" },
    withToken(user),
  );
}

export async function grantCardAccess(
  cardId: string,
  payload: { user_id: string; scope: string },
  user: AuthSession | null,
) {
  return request(`/client/cards/${cardId}/access`, { method: "POST", body: JSON.stringify(payload) }, withToken(user));
}

export async function revokeCardAccess(cardId: string, userId: string, user: AuthSession | null) {
  return request(`/client/cards/${cardId}/access/${userId}`, { method: "DELETE" }, withToken(user));
}

export async function fetchCardTransactions(cardId: string, user: AuthSession | null) {
  return request<
    { id: string; operation_type: string; status: string; amount: number; currency: string; performed_at: string }[]
  >(`/client/cards/${cardId}/transactions`, { method: "GET" }, withToken(user));
}
