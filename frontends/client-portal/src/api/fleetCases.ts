import { request } from "./http";
import { ApiError } from "./http";
import type { FleetCaseDetailsResponse, FleetCaseListResponse } from "../types/fleetCases";

const isFleetUnavailableError = (error: unknown): boolean =>
  error instanceof ApiError && (error.status === 404 || error.status === 501);

const handleAvailability = <T>(error: unknown, fallback: T): T => {
  if (isFleetUnavailableError(error)) {
    return fallback;
  }
  throw error;
};

type FleetCaseListParams = {
  status?: string;
  severity_min?: string;
  from?: string;
  to?: string;
  scope_type?: string;
  scope_id?: string;
};

export async function listFleetCases(
  token: string,
  params: FleetCaseListParams = {},
): Promise<FleetCaseListResponse> {
  const query = new URLSearchParams();
  if (params.status) query.set("status", params.status);
  if (params.severity_min) query.set("severity_min", params.severity_min);
  if (params.from) query.set("from", params.from);
  if (params.to) query.set("to", params.to);
  if (params.scope_type) query.set("scope_type", params.scope_type);
  if (params.scope_id) query.set("scope_id", params.scope_id);
  const suffix = query.toString();
  const path = suffix ? `/client/fleet/cases?${suffix}` : "/client/fleet/cases";
  try {
    const response = await request<{ items: FleetCaseListResponse["items"] }>(path, { method: "GET" }, { token });
    return { items: response.items ?? [] };
  } catch (error) {
    return handleAvailability(error, { items: [], unavailable: true });
  }
}

export async function getFleetCase(token: string, caseId: string): Promise<FleetCaseDetailsResponse> {
  try {
    const item = await request<FleetCaseDetailsResponse["item"]>(`/client/fleet/cases/${caseId}`, { method: "GET" }, { token });
    return { item: item ?? undefined };
  } catch (error) {
    return handleAvailability(error, { unavailable: true });
  }
}

export async function startFleetCase(token: string, caseId: string, note?: string): Promise<FleetCaseDetailsResponse> {
  try {
    const body = note ? JSON.stringify({ note }) : undefined;
    const item = await request<FleetCaseDetailsResponse["item"]>(
      `/client/fleet/cases/${caseId}/start`,
      { method: "POST", body },
      { token },
    );
    return { item: item ?? undefined };
  } catch (error) {
    return handleAvailability(error, { unavailable: true });
  }
}

export async function closeFleetCase(
  token: string,
  caseId: string,
  payload: { reason: string; resolution: string },
): Promise<FleetCaseDetailsResponse> {
  try {
    const item = await request<FleetCaseDetailsResponse["item"]>(
      `/client/fleet/cases/${caseId}/close`,
      { method: "POST", body: JSON.stringify(payload) },
      { token },
    );
    return { item: item ?? undefined };
  } catch (error) {
    return handleAvailability(error, { unavailable: true });
  }
}
