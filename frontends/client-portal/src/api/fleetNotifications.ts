import { ApiError, request } from "./http";
import type { FleetAlert, FleetNotificationChannel, FleetNotificationPolicy } from "../types/fleetNotifications";

export interface FleetNotificationsListResponse<T> {
  items: T[];
  unavailable?: boolean;
}

export interface FleetNotificationsEntityResponse<T> {
  item?: T;
  unavailable?: boolean;
}

const isNotificationsUnavailableError = (error: unknown): boolean =>
  error instanceof ApiError && (error.status === 404 || error.status === 501);

const handleAvailability = <T>(error: unknown, fallback: T): T => {
  if (isNotificationsUnavailableError(error)) {
    return fallback;
  }
  throw error;
};

export async function listAlerts(
  token: string,
  params?: { status?: string; severity_min?: string; from?: string; to?: string },
): Promise<FleetNotificationsListResponse<FleetAlert>> {
  const query = params ? new URLSearchParams(params).toString() : "";
  const suffix = query ? `?${query}` : "";
  try {
    const response = await request<{ items: FleetAlert[] }>(
      `/client/fleet/notifications/alerts${suffix}`,
      { method: "GET" },
      { token },
    );
    return { items: response.items ?? [] };
  } catch (error) {
    return handleAvailability(error, { items: [], unavailable: true });
  }
}

export async function ackAlert(token: string, id: string): Promise<FleetNotificationsEntityResponse<FleetAlert>> {
  try {
    const item = await request<FleetAlert>(
      `/client/fleet/notifications/alerts/${id}/ack`,
      { method: "POST" },
      { token },
    );
    return { item };
  } catch (error) {
    return handleAvailability(error, { unavailable: true });
  }
}

export async function ignoreAlert(
  token: string,
  id: string,
  payload: { reason: string },
): Promise<FleetNotificationsEntityResponse<FleetAlert>> {
  try {
    const item = await request<FleetAlert>(
      `/client/fleet/notifications/alerts/${id}/ignore`,
      { method: "POST", body: JSON.stringify(payload) },
      { token },
    );
    return { item };
  } catch (error) {
    return handleAvailability(error, { unavailable: true });
  }
}

export async function listChannels(token: string): Promise<FleetNotificationsListResponse<FleetNotificationChannel>> {
  try {
    const response = await request<{ items: FleetNotificationChannel[] }>(
      "/client/fleet/notifications/channels",
      { method: "GET" },
      { token },
    );
    return { items: response.items ?? [] };
  } catch (error) {
    return handleAvailability(error, { items: [], unavailable: true });
  }
}

export async function createChannel(
  token: string,
  payload: { channel_type: string; target: string; secret?: string },
): Promise<FleetNotificationsEntityResponse<FleetNotificationChannel>> {
  try {
    const item = await request<FleetNotificationChannel>(
      "/client/fleet/notifications/channels",
      { method: "POST", body: JSON.stringify(payload) },
      { token },
    );
    return { item };
  } catch (error) {
    return handleAvailability(error, { unavailable: true });
  }
}

export async function disableChannel(
  token: string,
  id: string,
): Promise<FleetNotificationsEntityResponse<FleetNotificationChannel>> {
  try {
    const item = await request<FleetNotificationChannel>(
      `/client/fleet/notifications/channels/${id}/disable`,
      { method: "POST" },
      { token },
    );
    return { item };
  } catch (error) {
    return handleAvailability(error, { unavailable: true });
  }
}

export async function listPolicies(token: string): Promise<FleetNotificationsListResponse<FleetNotificationPolicy>> {
  try {
    const response = await request<{ items: FleetNotificationPolicy[] }>(
      "/client/fleet/notifications/policies",
      { method: "GET" },
      { token },
    );
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
    event_type: string;
    severity_min: string;
    channel_ids: string[];
    cooldown_seconds: number;
    auto_action?: string;
  },
): Promise<FleetNotificationsEntityResponse<FleetNotificationPolicy>> {
  try {
    const item = await request<FleetNotificationPolicy>(
      "/client/fleet/notifications/policies",
      { method: "POST", body: JSON.stringify(payload) },
      { token },
    );
    return { item };
  } catch (error) {
    return handleAvailability(error, { unavailable: true });
  }
}

export async function disablePolicy(
  token: string,
  id: string,
): Promise<FleetNotificationsEntityResponse<FleetNotificationPolicy>> {
  try {
    const item = await request<FleetNotificationPolicy>(
      `/client/fleet/notifications/policies/${id}/disable`,
      { method: "POST" },
      { token },
    );
    return { item };
  } catch (error) {
    return handleAvailability(error, { unavailable: true });
  }
}
