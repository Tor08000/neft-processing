import { request, requestWithMeta } from "./http";
import type { AuthSession } from "./types";
import type {
  ClientFeaturesResponse,
  ClientLimitsResponse,
  ClientServicesResponse,
  ClientUsersResponse,
  ControlToggleResponse,
  CreateClientUserPayload,
  LimitChangeRequestPayload,
  LimitChangeRequestResponse,
  UpdateClientUserPayload,
} from "../types/controls";

const withToken = (user: AuthSession | null): string | undefined => user?.token;

export function fetchClientLimits(user: AuthSession | null): Promise<ClientLimitsResponse> {
  return request<ClientLimitsResponse>("/client/limits", { method: "GET" }, withToken(user));
}

export function requestLimitChange(user: AuthSession | null, payload: LimitChangeRequestPayload) {
  return requestWithMeta<LimitChangeRequestResponse>(
    "/client/limits/requests",
    { method: "POST", body: JSON.stringify(payload) },
    withToken(user),
  );
}

export function fetchClientUsers(user: AuthSession | null): Promise<ClientUsersResponse> {
  return request<ClientUsersResponse>("/client/users", { method: "GET" }, withToken(user));
}

export function createClientUser(user: AuthSession | null, payload: CreateClientUserPayload) {
  return requestWithMeta(
    "/client/users",
    { method: "POST", body: JSON.stringify(payload) },
    withToken(user),
  );
}

export function updateClientUserRole(user: AuthSession | null, userId: string, payload: UpdateClientUserPayload) {
  return requestWithMeta(
    `/client/users/${userId}`,
    { method: "PATCH", body: JSON.stringify(payload) },
    withToken(user),
  );
}

export function disableClientUser(user: AuthSession | null, userId: string) {
  return requestWithMeta(`/client/users/${userId}/disable`, { method: "POST" }, withToken(user));
}

export function fetchClientServices(user: AuthSession | null): Promise<ClientServicesResponse> {
  return request<ClientServicesResponse>("/client/services", { method: "GET" }, withToken(user));
}

export function toggleClientService(user: AuthSession | null, serviceId: string) {
  return requestWithMeta<ControlToggleResponse>(
    `/client/services/${serviceId}/toggle`,
    { method: "POST" },
    withToken(user),
  );
}

export function fetchClientFeatures(user: AuthSession | null): Promise<ClientFeaturesResponse> {
  return request<ClientFeaturesResponse>("/client/features", { method: "GET" }, withToken(user));
}

export function toggleClientFeature(user: AuthSession | null, featureKey: string) {
  return requestWithMeta<ControlToggleResponse>(
    `/client/features/${featureKey}/toggle`,
    { method: "POST" },
    withToken(user),
  );
}
