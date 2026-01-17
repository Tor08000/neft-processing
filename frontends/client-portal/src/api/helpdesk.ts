import { request } from "./http";
import type { AuthSession } from "./types";
import type {
  HelpdeskIntegrationPatch,
  HelpdeskIntegrationPayload,
  HelpdeskIntegrationResponse,
  HelpdeskTicketLinkResponse,
} from "../types/helpdesk";

const withToken = (user: AuthSession | null): string | undefined => user?.token;

export const fetchHelpdeskIntegration = (user: AuthSession | null) =>
  request<HelpdeskIntegrationResponse>("/client/helpdesk/integration", { method: "GET" }, withToken(user));

export const enableHelpdeskIntegration = (payload: HelpdeskIntegrationPayload, user: AuthSession | null) =>
  request<HelpdeskIntegrationResponse>(
    "/client/helpdesk/integration",
    { method: "POST", body: JSON.stringify(payload) },
    withToken(user),
  );

export const updateHelpdeskIntegration = (payload: HelpdeskIntegrationPatch, user: AuthSession | null) =>
  request<HelpdeskIntegrationResponse>(
    "/client/helpdesk/integration",
    { method: "PATCH", body: JSON.stringify(payload) },
    withToken(user),
  );

export const disableHelpdeskIntegration = (user: AuthSession | null) =>
  request<HelpdeskIntegrationResponse>(
    "/client/helpdesk/integration/disable",
    { method: "POST" },
    withToken(user),
  );

export const fetchHelpdeskTicketLink = (ticketId: string, user: AuthSession | null) =>
  request<HelpdeskTicketLinkResponse>(
    `/client/helpdesk/tickets/${ticketId}/link`,
    { method: "GET" },
    withToken(user),
  );
