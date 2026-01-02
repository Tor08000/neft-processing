import { request } from "./http";
import { ApiError } from "./http";
import type {
  FleetPolicy,
  FleetPolicyExecution,
  FleetPolicyExecutionFilters,
} from "../types/fleetPolicies";

export interface FleetPoliciesListResponse<T> {
  items: T[];
  unavailable?: boolean;
}

export interface FleetPoliciesEntityResponse<T> {
  item?: T;
  unavailable?: boolean;
}

const isFleetPoliciesUnavailableError = (error: unknown): boolean =>
  error instanceof ApiError && (error.status === 404 || error.status === 501);

const handleAvailability = <T>(error: unknown, fallback: T): T => {
  if (isFleetPoliciesUnavailableError(error)) {
    return fallback;
  }
  throw error;
};

export async function listPolicies(token: string): Promise<FleetPoliciesListResponse<FleetPolicy>> {
  try {
    const response = await request<{ items: FleetPolicy[] }>("/client/fleet/policies", { method: "GET" }, { token });
    return { items: response.items ?? [] };
  } catch (error) {
    return handleAvailability(error, { items: [], unavailable: true });
  }
}

export async function createPolicy(
  token: string,
  payload: {
    scope_type: string;
    scope_id?: string;
    trigger_type: string;
    severity_min: string;
    breach_kind?: string;
    action: string;
    cooldown_seconds: number;
  },
): Promise<FleetPoliciesEntityResponse<FleetPolicy>> {
  try {
    const item = await request<FleetPolicy>(
      "/client/fleet/policies",
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
      { token },
    );
    return { item };
  } catch (error) {
    return handleAvailability(error, { unavailable: true });
  }
}

export async function disablePolicy(token: string, id: string): Promise<FleetPoliciesEntityResponse<FleetPolicy>> {
  try {
    const item = await request<FleetPolicy>(`/client/fleet/policies/${id}/disable`, { method: "POST" }, { token });
    return { item };
  } catch (error) {
    return handleAvailability(error, { unavailable: true });
  }
}

export async function listExecutions(
  token: string,
  filters?: FleetPolicyExecutionFilters,
): Promise<FleetPoliciesListResponse<FleetPolicyExecution>> {
  const searchParams = new URLSearchParams();
  if (filters) {
    Object.entries(filters).forEach(([key, value]) => {
      if (value) {
        searchParams.set(key, value);
      }
    });
  }
  const query = searchParams.toString();
  const suffix = query ? `?${query}` : "";
  try {
    const response = await request<{ items: FleetPolicyExecution[] }>(
      `/client/fleet/policies/executions${suffix}`,
      { method: "GET" },
      { token },
    );
    return { items: response.items ?? [] };
  } catch (error) {
    return handleAvailability(error, { items: [], unavailable: true });
  }
}
