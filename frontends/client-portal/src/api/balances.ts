import { request } from "./http";
import type { AuthSession } from "./types";
import type { BalancesResponse } from "../types/balances";

const withToken = (user: AuthSession | null): string | undefined => user?.token;

export function fetchBalances(user: AuthSession | null): Promise<BalancesResponse> {
  return request<BalancesResponse>("/balances", { method: "GET" }, withToken(user));
}
