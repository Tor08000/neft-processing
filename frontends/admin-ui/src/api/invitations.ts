import { apiGet, apiPost } from "./client";

export interface AdminInvitationSummary {
  invitation_id: string;
  email: string;
  role?: string | null;
  status: string;
  created_at: string;
  expires_at: string;
  resent_count: number;
}

export interface AdminInvitationsResponse {
  items: AdminInvitationSummary[];
  total: number;
}

export async function listAdminInvitations(params?: {
  client_id?: string;
  status?: string;
  q?: string;
  sort?: string;
}) {
  return apiGet<AdminInvitationsResponse>("/v1/admin/clients/invitations", params);
}

export async function listClientInvitations(clientId: string, params?: { status?: string; q?: string; sort?: string }) {
  return apiGet<AdminInvitationsResponse>(`/v1/admin/clients/${clientId}/invitations`, params);
}

export async function resendInvitation(invitationId: string) {
  return apiPost(`/v1/admin/clients/invitations/${invitationId}/resend`);
}

export async function revokeInvitation(invitationId: string) {
  return apiPost(`/v1/admin/clients/invitations/${invitationId}/revoke`);
}
