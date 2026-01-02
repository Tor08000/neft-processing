import { request } from "./http";
import type {
  FleetCard,
  FleetEmployee,
  FleetGroup,
  FleetLimit,
  FleetSpendSummary,
  FleetTransaction,
} from "../types/fleet";

export interface FleetListResponse<T> {
  items: T[];
  unavailable?: boolean;
}

export interface FleetSpendSummaryResponse extends FleetSpendSummary {
  unavailable?: boolean;
}

const isNotAvailableMessage = (message?: string) => Boolean(message && /HTTP (404|501)\b/.test(message));

export const isNotAvailableError = (error: unknown): boolean => {
  if (error instanceof Error) {
    return isNotAvailableMessage(error.message);
  }
  return false;
};

const handleAvailability = <T>(error: unknown, fallback: T): T => {
  if (isNotAvailableError(error)) {
    return fallback;
  }
  throw error;
};

export async function listFleetCards(token: string): Promise<FleetListResponse<FleetCard>> {
  try {
    const response = await request<{ items: FleetCard[] }>("/client/fleet/cards", { method: "GET" }, { token });
    return { items: response.items ?? [] };
  } catch (error) {
    return handleAvailability(error, { items: [], unavailable: true });
  }
}

export async function listFleetGroups(token: string): Promise<FleetListResponse<FleetGroup>> {
  try {
    const response = await request<{ items: FleetGroup[] }>("/client/fleet/groups", { method: "GET" }, { token });
    return { items: response.items ?? [] };
  } catch (error) {
    return handleAvailability(error, { items: [], unavailable: true });
  }
}

export async function listFleetEmployees(token: string): Promise<FleetListResponse<FleetEmployee>> {
  try {
    const response = await request<{ items: FleetEmployee[] }>("/client/fleet/employees", { method: "GET" }, { token });
    return { items: response.items ?? [] };
  } catch (error) {
    return handleAvailability(error, { items: [], unavailable: true });
  }
}

export async function listFleetLimits(
  token: string,
  params: { scope_type: string; scope_id: string },
): Promise<FleetListResponse<FleetLimit>> {
  const query = new URLSearchParams(params).toString();
  try {
    const response = await request<{ items: FleetLimit[] }>(`/client/fleet/limits?${query}`, { method: "GET" }, { token });
    return { items: response.items ?? [] };
  } catch (error) {
    return handleAvailability(error, { items: [], unavailable: true });
  }
}

export async function listFleetTransactions(
  token: string,
  params?: { card_id?: string; group_id?: string; date_from?: string; date_to?: string },
): Promise<FleetListResponse<FleetTransaction>> {
  const query = params ? new URLSearchParams(params).toString() : "";
  const suffix = query ? `?${query}` : "";
  try {
    const response = await request<{ items: FleetTransaction[] }>(`/client/fleet/transactions${suffix}`, { method: "GET" }, { token });
    return { items: response.items ?? [] };
  } catch (error) {
    return handleAvailability(error, { items: [], unavailable: true });
  }
}

export async function getFleetSpendSummary(
  token: string,
  params?: { group_by?: string; card_id?: string; group_id?: string; date_from?: string; date_to?: string },
): Promise<FleetSpendSummaryResponse> {
  const query = params ? new URLSearchParams(params).toString() : "";
  const suffix = query ? `?${query}` : "";
  try {
    return await request<FleetSpendSummary>(`/client/fleet/spend/summary${suffix}`, { method: "GET" }, { token });
  } catch (error) {
    return handleAvailability(error, { group_by: params?.group_by ?? "day", rows: [], unavailable: true });
  }
}
