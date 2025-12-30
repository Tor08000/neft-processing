import { request } from "./http";
import type { AuthSession } from "./types";
import type { SpendDashboardResponse } from "../types/spend";

const withToken = (user: AuthSession | null): string | undefined => user?.token;

export function fetchSpendDashboard(user: AuthSession | null): Promise<SpendDashboardResponse> {
  return request<SpendDashboardResponse>("/dashboard", { method: "GET" }, withToken(user));
}
