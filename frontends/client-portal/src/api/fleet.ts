import { request } from "./http";
import type {
  FleetAccess,
  FleetCard,
  FleetEmployee,
  FleetExportResponse,
  FleetGroup,
  FleetLimit,
  FleetSpendSummary,
  FleetTransaction,
} from "../types/fleet";
import { ApiError, HtmlResponseError } from "./http";

export interface FleetListResponse<T> {
  items: T[];
  unavailable?: boolean;
}

export interface FleetEntityResponse<T> {
  item?: T;
  unavailable?: boolean;
}

export interface FleetSpendSummaryResponse extends FleetSpendSummary {
  unavailable?: boolean;
}

const isFleetUnavailableError = (error: unknown): boolean => {
  if (error instanceof ApiError || error instanceof HtmlResponseError) {
    return error.status === 404 || error.status === 501;
  }
  return false;
};

const handleAvailability = <T>(error: unknown, fallback: T): T => {
  if (isFleetUnavailableError(error)) {
    return fallback;
  }
  throw error;
};

export async function listCards(
  token: string,
  params?: { status?: string; q?: string },
): Promise<FleetListResponse<FleetCard>> {
  const query = params ? new URLSearchParams(params).toString() : "";
  const suffix = query ? `?${query}` : "";
  try {
    const response = await request<{ items: FleetCard[] }>(`/client/fleet/cards${suffix}`, { method: "GET" }, { token });
    return { items: response.items ?? [] };
  } catch (error) {
    return handleAvailability(error, { items: [], unavailable: true });
  }
}

export async function createCard(
  token: string,
  payload: { card_alias: string; masked_pan: string },
): Promise<FleetEntityResponse<FleetCard>> {
  try {
    const item = await request<FleetCard>("/client/fleet/cards", {
      method: "POST",
      body: JSON.stringify(payload),
    }, { token });
    return { item };
  } catch (error) {
    return handleAvailability(error, { unavailable: true });
  }
}

export async function getCard(token: string, id: string): Promise<FleetEntityResponse<FleetCard>> {
  try {
    const item = await request<FleetCard>(`/client/fleet/cards/${id}`, { method: "GET" }, { token });
    return { item };
  } catch (error) {
    return handleAvailability(error, { unavailable: true });
  }
}

export async function blockCard(token: string, id: string): Promise<FleetEntityResponse<FleetCard>> {
  try {
    const item = await request<FleetCard>(`/client/fleet/cards/${id}/block`, { method: "POST" }, { token });
    return { item };
  } catch (error) {
    return handleAvailability(error, { unavailable: true });
  }
}

export async function unblockCard(token: string, id: string): Promise<FleetEntityResponse<FleetCard>> {
  try {
    const item = await request<FleetCard>(`/client/fleet/cards/${id}/unblock`, { method: "POST" }, { token });
    return { item };
  } catch (error) {
    return handleAvailability(error, { unavailable: true });
  }
}

export async function listGroups(token: string): Promise<FleetListResponse<FleetGroup>> {
  try {
    const response = await request<{ items: FleetGroup[] }>("/client/fleet/groups", { method: "GET" }, { token });
    return { items: response.items ?? [] };
  } catch (error) {
    return handleAvailability(error, { items: [], unavailable: true });
  }
}

export async function createGroup(
  token: string,
  payload: { name: string; description?: string },
): Promise<FleetEntityResponse<FleetGroup>> {
  try {
    const item = await request<FleetGroup>("/client/fleet/groups", {
      method: "POST",
      body: JSON.stringify(payload),
    }, { token });
    return { item };
  } catch (error) {
    return handleAvailability(error, { unavailable: true });
  }
}

export async function getGroup(token: string, id: string): Promise<FleetEntityResponse<FleetGroup>> {
  try {
    const response = await listGroups(token);
    if (response.unavailable) return { unavailable: true };
    const item = response.items.find((group) => group.id === id);
    if (!item) {
      throw new Error("Group not found");
    }
    return { item };
  } catch (error) {
    return handleAvailability(error, { unavailable: true });
  }
}

export async function addCardToGroup(
  token: string,
  groupId: string,
  cardId: string,
): Promise<FleetEntityResponse<{ group_id: string; card_id: string }>> {
  try {
    const item = await request<{ group_id: string; card_id: string }>(`/client/fleet/groups/${groupId}/members/add`, {
      method: "POST",
      body: JSON.stringify({ card_id: cardId }),
    }, { token });
    return { item };
  } catch (error) {
    return handleAvailability(error, { unavailable: true });
  }
}

export async function removeCardFromGroup(
  token: string,
  groupId: string,
  cardId: string,
): Promise<FleetEntityResponse<{ group_id: string; card_id: string }>> {
  try {
    const item = await request<{ group_id: string; card_id: string }>(`/client/fleet/groups/${groupId}/members/remove`, {
      method: "POST",
      body: JSON.stringify({ card_id: cardId }),
    }, { token });
    return { item };
  } catch (error) {
    return handleAvailability(error, { unavailable: true });
  }
}

export async function listEmployees(token: string): Promise<FleetListResponse<FleetEmployee>> {
  try {
    const response = await request<{ items: FleetEmployee[] }>("/client/fleet/employees", { method: "GET" }, { token });
    return { items: response.items ?? [] };
  } catch (error) {
    return handleAvailability(error, { items: [], unavailable: true });
  }
}

export async function inviteEmployee(
  token: string,
  payload: { email: string },
): Promise<FleetEntityResponse<FleetEmployee>> {
  try {
    const item = await request<FleetEmployee>("/client/fleet/employees/invite", {
      method: "POST",
      body: JSON.stringify(payload),
    }, { token });
    return { item };
  } catch (error) {
    return handleAvailability(error, { unavailable: true });
  }
}

export async function disableEmployee(token: string, id: string): Promise<FleetEntityResponse<FleetEmployee>> {
  try {
    const item = await request<FleetEmployee>(`/client/fleet/employees/${id}/disable`, { method: "POST" }, { token });
    return { item };
  } catch (error) {
    return handleAvailability(error, { unavailable: true });
  }
}

export async function listGroupAccess(
  token: string,
  groupId: string,
): Promise<FleetListResponse<FleetAccess>> {
  try {
    const response = await request<{ items: FleetAccess[] }>(`/client/fleet/groups/${groupId}/access`, { method: "GET" }, { token });
    return { items: response.items ?? [] };
  } catch (error) {
    return handleAvailability(error, { items: [], unavailable: true });
  }
}

export async function grantGroupAccess(
  token: string,
  groupId: string,
  payload: { employee_id: string; role: string },
): Promise<FleetEntityResponse<FleetAccess>> {
  try {
    const item = await request<FleetAccess>(`/client/fleet/groups/${groupId}/access/grant`, {
      method: "POST",
      body: JSON.stringify(payload),
    }, { token });
    return { item };
  } catch (error) {
    return handleAvailability(error, { unavailable: true });
  }
}

export async function revokeGroupAccess(
  token: string,
  groupId: string,
  payload: { employee_id: string },
): Promise<FleetEntityResponse<FleetAccess>> {
  try {
    const item = await request<FleetAccess>(`/client/fleet/groups/${groupId}/access/revoke`, {
      method: "POST",
      body: JSON.stringify(payload),
    }, { token });
    return { item };
  } catch (error) {
    return handleAvailability(error, { unavailable: true });
  }
}

export async function listLimits(
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

export async function setLimit(
  token: string,
  payload: {
    scope_type: string;
    scope_id: string;
    period: string;
    amount_limit?: number | string | null;
    volume_limit_liters?: number | string | null;
    categories?: Record<string, unknown> | null;
    stations_allowlist?: Record<string, unknown> | null;
    effective_from?: string | null;
  },
): Promise<FleetEntityResponse<FleetLimit>> {
  try {
    const item = await request<FleetLimit>("/client/fleet/limits/set", {
      method: "POST",
      body: JSON.stringify(payload),
    }, { token });
    return { item };
  } catch (error) {
    return handleAvailability(error, { unavailable: true });
  }
}

export async function revokeLimit(
  token: string,
  payload: { limit_id: string },
): Promise<FleetEntityResponse<FleetLimit>> {
  try {
    const item = await request<FleetLimit>("/client/fleet/limits/revoke", {
      method: "POST",
      body: JSON.stringify(payload),
    }, { token });
    return { item };
  } catch (error) {
    return handleAvailability(error, { unavailable: true });
  }
}

export async function listTransactions(
  token: string,
  params?: {
    from?: string;
    to?: string;
    card_id?: string;
    group_id?: string;
    category?: string;
    merchant?: string;
    page?: number;
    page_size?: number;
  },
): Promise<FleetListResponse<FleetTransaction>> {
  const queryParams = new URLSearchParams();
  if (params?.from) queryParams.set("date_from", params.from);
  if (params?.to) queryParams.set("date_to", params.to);
  if (params?.card_id) queryParams.set("card_id", params.card_id);
  if (params?.group_id) queryParams.set("group_id", params.group_id);
  if (params?.category) queryParams.set("category", params.category);
  if (params?.merchant) queryParams.set("merchant", params.merchant);
  if (params?.page_size) queryParams.set("limit", String(params.page_size));
  if (params?.page !== undefined && params.page_size) {
    queryParams.set("offset", String(params.page * params.page_size));
  }
  const suffix = queryParams.toString() ? `?${queryParams.toString()}` : "";
  try {
    const response = await request<{ items: FleetTransaction[] }>(`/client/fleet/transactions${suffix}`, { method: "GET" }, { token });
    return { items: response.items ?? [] };
  } catch (error) {
    return handleAvailability(error, { items: [], unavailable: true });
  }
}

export async function getSpendSummary(
  token: string,
  params?: { from?: string; to?: string; group_by: string; card_id?: string; group_id?: string },
): Promise<FleetSpendSummaryResponse> {
  const queryParams = new URLSearchParams();
  if (params?.from) queryParams.set("date_from", params.from);
  if (params?.to) queryParams.set("date_to", params.to);
  if (params?.group_by) queryParams.set("group_by", params.group_by);
  if (params?.card_id) queryParams.set("card_id", params.card_id);
  if (params?.group_id) queryParams.set("group_id", params.group_id);
  const suffix = queryParams.toString() ? `?${queryParams.toString()}` : "";
  try {
    return await request<FleetSpendSummary>(`/client/fleet/spend/summary${suffix}`, { method: "GET" }, { token });
  } catch (error) {
    return handleAvailability(error, { group_by: params?.group_by ?? "day", rows: [], unavailable: true });
  }
}

export async function exportTransactions(
  token: string,
  params: { from?: string; to?: string; card_id?: string; group_id?: string; format?: string },
): Promise<FleetEntityResponse<FleetExportResponse>> {
  const queryParams = new URLSearchParams();
  if (params.from) queryParams.set("date_from", params.from);
  if (params.to) queryParams.set("date_to", params.to);
  if (params.card_id) queryParams.set("card_id", params.card_id);
  if (params.group_id) queryParams.set("group_id", params.group_id);
  if (params.format) queryParams.set("format", params.format);
  const suffix = queryParams.toString() ? `?${queryParams.toString()}` : "";
  try {
    const item = await request<FleetExportResponse>(`/client/fleet/transactions/export${suffix}`, { method: "GET" }, { token });
    return { item };
  } catch (error) {
    return handleAvailability(error, { unavailable: true });
  }
}

export async function downloadTransactionsExport(
  token: string,
  exportId: string,
): Promise<FleetEntityResponse<FleetExportResponse>> {
  try {
    const item = await request<FleetExportResponse>(`/client/fleet/transactions/export/${exportId}`, { method: "GET" }, { token });
    return { item };
  } catch (error) {
    return handleAvailability(error, { unavailable: true });
  }
}
