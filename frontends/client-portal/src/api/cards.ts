import { request } from "./http";
import type { CardLimit, ClientCard, ClientCardsResponse } from "../types/cards";
import type { AuthSession } from "./types";

const withToken = (user: AuthSession | null): string | undefined => user?.token;

export async function fetchCards(user: AuthSession | null): Promise<ClientCardsResponse> {
  return request<ClientCardsResponse>("/cards", { method: "GET" }, withToken(user));
}

export async function fetchCard(cardId: string, user: AuthSession | null): Promise<ClientCard> {
  return request<ClientCard>(`/cards/${cardId}`, { method: "GET" }, withToken(user));
}

export async function blockCard(cardId: string, user: AuthSession | null): Promise<{ status: string }>
{
  return request<{ status: string }>(`/cards/${cardId}/block`, { method: "POST" }, withToken(user));
}

export async function unblockCard(
  cardId: string,
  user: AuthSession | null,
): Promise<{ status: string }> {
  return request<{ status: string }>(`/cards/${cardId}/unblock`, { method: "POST" }, withToken(user));
}

export async function updateCardLimit(
  cardId: string,
  payload: CardLimit,
  user: AuthSession | null,
): Promise<ClientCard> {
  return request<ClientCard>(`/cards/${cardId}/limits`, { method: "POST", body: JSON.stringify(payload) }, withToken(user));
}
